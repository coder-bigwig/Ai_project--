from typing import Optional

from fastapi import APIRouter, HTTPException


def _get_main_module():
    from ... import main
    return main


main = _get_main_module()
router = APIRouter()


async def create_experiment(experiment: main.Experiment):
    """创建新实验"""
    normalized_teacher = main._normalize_text(experiment.created_by)
    main._ensure_teacher(normalized_teacher)
    experiment.created_by = normalized_teacher

    course_record, _ = main._resolve_or_create_teacher_course(
        normalized_teacher,
        main._resolve_course_name(experiment),
        experiment.course_id,
    )

    experiment.id = str(main.uuid.uuid4())
    experiment.created_at = main.datetime.now()
    experiment.course_id = course_record.id
    experiment.course_name = course_record.name
    main._normalize_experiment_publish_targets(experiment)
    main._validate_experiment_publish_targets(experiment)
    main.experiments_db[experiment.id] = experiment

    course_record.updated_at = experiment.created_at
    main._save_course_registry()
    main._save_experiment_registry()
    return experiment


async def list_experiments(
    difficulty: Optional[main.DifficultyLevel] = None,
    tag: Optional[str] = None,
    username: Optional[str] = None,
):
    """获取实验列表（支持筛选）"""
    experiments = list(main.experiments_db.values())

    normalized_username = main._normalize_text(username)
    # 学生只能看到自己可见实验
    if normalized_username and not (main.is_teacher(normalized_username) or main.is_admin(normalized_username)):
        student = main.students_db.get(normalized_username)
        if not student:
            experiments = []
        else:
            experiments = [e for e in experiments if main._is_experiment_visible_to_student(e, student)]

    if difficulty:
        experiments = [e for e in experiments if e.difficulty == difficulty]

    if tag:
        experiments = [e for e in experiments if tag in e.tags]

    return experiments


async def get_experiment(experiment_id: str):
    """获取实验详情"""
    if experiment_id not in main.experiments_db:
        raise HTTPException(status_code=404, detail="实验不存在")
    return main.experiments_db[experiment_id]


async def update_experiment(experiment_id: str, experiment: main.Experiment):
    """更新实验"""
    if experiment_id not in main.experiments_db:
        raise HTTPException(status_code=404, detail="实验不存在")

    existing = main.experiments_db[experiment_id]
    experiment.id = experiment_id
    if experiment.created_at is None:
        experiment.created_at = existing.created_at
    if not experiment.created_by:
        experiment.created_by = existing.created_by

    normalized_teacher = main._normalize_text(experiment.created_by)
    main._ensure_teacher(normalized_teacher)
    experiment.created_by = normalized_teacher

    requested_course_id = experiment.course_id or existing.course_id
    requested_course_name = main._resolve_course_name(experiment)
    if not main._normalize_text(experiment.course_name):
        requested_course_name = main._resolve_course_name(existing)

    course_record, _ = main._resolve_or_create_teacher_course(
        normalized_teacher,
        requested_course_name,
        requested_course_id,
    )

    experiment.course_id = course_record.id
    experiment.course_name = course_record.name
    main._normalize_experiment_publish_targets(experiment)
    main._validate_experiment_publish_targets(experiment)
    main.experiments_db[experiment_id] = experiment
    course_record.updated_at = main.datetime.now()
    main._save_course_registry()
    main._save_experiment_registry()
    return experiment


async def delete_experiment(experiment_id: str):
    """删除实验"""
    if experiment_id not in main.experiments_db:
        raise HTTPException(status_code=404, detail="实验不存在")

    removed_attachment_ids = [
        att_id
        for att_id, item in main.attachments_db.items()
        if item.experiment_id == experiment_id
    ]
    for att_id in removed_attachment_ids:
        item = main.attachments_db.pop(att_id, None)
        if item and main.os.path.exists(item.file_path):
            try:
                main.os.remove(item.file_path)
            except OSError:
                pass
    if removed_attachment_ids:
        main._save_attachment_registry()

    removed_exp = main.experiments_db.pop(experiment_id)
    course_id = main._normalize_text(removed_exp.course_id)
    if course_id and course_id in main.courses_db:
        main.courses_db[course_id].updated_at = main.datetime.now()
        main._save_course_registry()

    main._save_experiment_registry()
    return {"message": "实验已删除"}


router.add_api_route("/api/experiments", create_experiment, methods=["POST"], response_model=main.Experiment)
router.add_api_route("/api/experiments", list_experiments, methods=["GET"], response_model=list[main.Experiment])
router.add_api_route("/api/experiments/{experiment_id}", get_experiment, methods=["GET"], response_model=main.Experiment)
router.add_api_route("/api/experiments/{experiment_id}", update_experiment, methods=["PUT"], response_model=main.Experiment)
router.add_api_route("/api/experiments/{experiment_id}", delete_experiment, methods=["DELETE"])
