# experiment_manager.py - 实验管理核心API

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from enum import Enum
import uuid

app = FastAPI(title="实训平台 - 实验管理API")

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== 数据模型 ====================

class DifficultyLevel(str, Enum):
    BEGINNER = "初级"
    INTERMEDIATE = "中级"
    ADVANCED = "高级"

class ExperimentStatus(str, Enum):
    NOT_STARTED = "未开始"
    IN_PROGRESS = "进行中"
    SUBMITTED = "已提交"
    GRADED = "已评分"

class Experiment(BaseModel):
    id: str = None
    title: str
    description: str
    difficulty: DifficultyLevel
    tags: List[str] = []
    notebook_path: str
    resources: dict = {"cpu": 1.0, "memory": "2G", "storage": "1G"}
    deadline: Optional[datetime] = None
    created_at: datetime = None
    created_by: str
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class StudentExperiment(BaseModel):
    id: str = None
    experiment_id: str
    student_id: str
    status: ExperimentStatus = ExperimentStatus.NOT_STARTED
    start_time: Optional[datetime] = None
    submit_time: Optional[datetime] = None
    notebook_content: Optional[str] = None
    score: Optional[float] = None
    ai_feedback: Optional[str] = None
    teacher_comment: Optional[str] = None

class SubmitExperimentRequest(BaseModel):
    notebook_content: str

# ==================== 模拟数据库 ====================
# 生产环境应使用 PostgreSQL + SQLAlchemy

experiments_db = {}
student_experiments_db = {}

# ==================== API端点 ====================

@app.get("/")
def root():
    return {"message": "实训平台 API", "version": "1.0.0"}

# ---------- 实验管理 ----------

@app.post("/api/experiments", response_model=Experiment)
async def create_experiment(experiment: Experiment):
    """创建新实验"""
    experiment.id = str(uuid.uuid4())
    experiment.created_at = datetime.now()
    experiments_db[experiment.id] = experiment
    return experiment

@app.get("/api/experiments", response_model=List[Experiment])
async def list_experiments(
    difficulty: Optional[DifficultyLevel] = None,
    tag: Optional[str] = None
):
    """获取实验列表（支持筛选）"""
    experiments = list(experiments_db.values())
    
    if difficulty:
        experiments = [e for e in experiments if e.difficulty == difficulty]
    
    if tag:
        experiments = [e for e in experiments if tag in e.tags]
    
    return experiments

@app.get("/api/experiments/{experiment_id}", response_model=Experiment)
async def get_experiment(experiment_id: str):
    """获取实验详情"""
    if experiment_id not in experiments_db:
        raise HTTPException(status_code=404, detail="实验不存在")
    return experiments_db[experiment_id]

@app.put("/api/experiments/{experiment_id}", response_model=Experiment)
async def update_experiment(experiment_id: str, experiment: Experiment):
    """更新实验"""
    if experiment_id not in experiments_db:
        raise HTTPException(status_code=404, detail="实验不存在")
    
    experiment.id = experiment_id
    experiments_db[experiment_id] = experiment
    return experiment

@app.delete("/api/experiments/{experiment_id}")
async def delete_experiment(experiment_id: str):
    """删除实验"""
    if experiment_id not in experiments_db:
        raise HTTPException(status_code=404, detail="实验不存在")
    
    del experiments_db[experiment_id]
    return {"message": "实验已删除"}

# ---------- 学生实验管理 ----------

@app.post("/api/student-experiments/start/{experiment_id}")
async def start_experiment(experiment_id: str, student_id: str):
    """学生开始实验"""
    if experiment_id not in experiments_db:
        raise HTTPException(status_code=404, detail="实验不存在")
    
    student_exp = StudentExperiment(
        id=str(uuid.uuid4()),
        experiment_id=experiment_id,
        student_id=student_id,
        status=ExperimentStatus.IN_PROGRESS,
        start_time=datetime.now()
    )
    
    student_experiments_db[student_exp.id] = student_exp
    
    return {
        "student_experiment_id": student_exp.id,
        "jupyter_url": f"/user/{student_id}/lab",
        "message": "实验环境已启动"
    }

@app.post("/api/student-experiments/{student_exp_id}/submit")
async def submit_experiment(
    student_exp_id: str,
    submission: SubmitExperimentRequest
):
    """提交实验"""
    if student_exp_id not in student_experiments_db:
        raise HTTPException(status_code=404, detail="学生实验记录不存在")
    
    student_exp = student_experiments_db[student_exp_id]
    student_exp.notebook_content = submission.notebook_content
    student_exp.status = ExperimentStatus.SUBMITTED
    student_exp.submit_time = datetime.now()
    
    # 触发AI自动评分（异步任务）
    # await trigger_ai_grading(student_exp_id)
    
    return {
        "message": "实验已提交",
        "submit_time": student_exp.submit_time
    }

@app.get("/api/student-experiments/my-experiments/{student_id}")
async def get_student_experiments(student_id: str):
    """获取学生的所有实验"""
    student_exps = [
        exp for exp in student_experiments_db.values()
        if exp.student_id == student_id
    ]
    return student_exps

@app.get("/api/student-experiments/{student_exp_id}")
async def get_student_experiment_detail(student_exp_id: str):
    """获取学生实验详情"""
    if student_exp_id not in student_experiments_db:
        raise HTTPException(status_code=404, detail="学生实验记录不存在")
    return student_experiments_db[student_exp_id]

# ---------- 教师功能 ----------

@app.get("/api/teacher/experiments/{experiment_id}/submissions")
async def get_experiment_submissions(experiment_id: str):
    """教师查看某个实验的所有提交"""
    submissions = [
        exp for exp in student_experiments_db.values()
        if exp.experiment_id == experiment_id
    ]
    return submissions

@app.post("/api/teacher/grade/{student_exp_id}")
async def grade_experiment(
    student_exp_id: str,
    score: float,
    comment: Optional[str] = None
):
    """教师评分"""
    if student_exp_id not in student_experiments_db:
        raise HTTPException(status_code=404, detail="学生实验记录不存在")
    
    if not (0 <= score <= 100):
        raise HTTPException(status_code=400, detail="分数必须在0-100之间")
    
    student_exp = student_experiments_db[student_exp_id]
    student_exp.score = score
    student_exp.teacher_comment = comment
    student_exp.status = ExperimentStatus.GRADED
    
    return {
        "message": "评分成功",
        "score": score
    }

@app.get("/api/teacher/statistics")
async def get_statistics():
    """获取统计数据"""
    total_experiments = len(experiments_db)
    total_submissions = len(student_experiments_db)
    
    status_count = {}
    for exp in student_experiments_db.values():
        status_count[exp.status.value] = status_count.get(exp.status.value, 0) + 1
    
    return {
        "total_experiments": total_experiments,
        "total_submissions": total_submissions,
        "status_distribution": status_count
    }

# ==================== AI集成接口 ====================

@app.post("/api/ai/code-review")
async def ai_code_review(code: str, language: str = "python"):
    """AI代码审查"""
    # 这里集成AI模型进行代码审查
    # 示例返回
    return {
        "issues": [
            {"line": 5, "type": "warning", "message": "变量名不规范"},
            {"line": 12, "type": "error", "message": "缺少异常处理"}
        ],
        "suggestions": [
            "建议添加类型注解",
            "考虑使用列表推导式优化性能"
        ],
        "overall_score": 85
    }

@app.post("/api/ai/explain-code")
async def ai_explain_code(code: str):
    """AI代码解释"""
    return {
        "explanation": "这段代码实现了...",
        "key_concepts": ["循环", "条件判断", "列表操作"],
        "complexity": "O(n)"
    }

@app.post("/api/ai/debug-help")
async def ai_debug_help(code: str, error_message: str):
    """AI调试帮助"""
    return {
        "possible_causes": [
            "数组越界",
            "类型不匹配"
        ],
        "suggestions": [
            "检查循环索引范围",
            "使用try-except捕获异常"
        ],
        "fixed_code": "# 修复后的代码..."
    }

@app.post("/api/ai/chat")
async def ai_chat(question: str, context: Optional[str] = None):
    """AI问答助手"""
    return {
        "answer": "根据你的问题...",
        "related_topics": ["Python基础", "数据结构"],
        "references": ["官方文档链接"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
