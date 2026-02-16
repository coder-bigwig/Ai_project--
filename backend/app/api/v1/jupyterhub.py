from typing import Optional

from fastapi import APIRouter, HTTPException


def _get_main_module():
    from ... import main
    return main


router = APIRouter()


async def get_jupyterhub_auto_login_url(username: str, experiment_id: Optional[str] = None):
    """Return a tokenized JupyterLab URL so portal users don't need a second Hub login."""
    main = _get_main_module()
    user = main._normalize_text(username)
    if not user:
        raise HTTPException(status_code=400, detail="username不能为空")

    target_experiment = None
    notebook_relpath = None
    normalized_experiment_id = main._normalize_text(experiment_id)
    if normalized_experiment_id:
        target_experiment = main.experiments_db.get(normalized_experiment_id)
        if not target_experiment:
            raise HTTPException(status_code=404, detail="实验不存在")

        if not (main.is_teacher(user) or main.is_admin(user)):
            main._ensure_student(user)
            student = main.students_db[user]
            if not main._is_experiment_visible_to_student(target_experiment, student):
                raise HTTPException(status_code=403, detail="该实验当前未发布给你")

        notebook_relpath = f"work/{user}_{normalized_experiment_id[:8]}.ipynb"

    if not main._jupyterhub_enabled():
        path = notebook_relpath
        return {
            "jupyter_url": main._build_user_lab_url(user, path=path) if path else f"{main.JUPYTERHUB_PUBLIC_URL}/hub/home",
            "tokenized": False,
            "message": "JupyterHub token integration is disabled",
        }

    if not main._ensure_user_server_running(user):
        raise HTTPException(status_code=503, detail="JupyterHub user server failed to start")

    token = main._create_short_lived_user_token(user)
    if target_experiment and token:
        try:
            # Ensure work directory exists in the user's server.
            dir_resp = main._user_contents_request(user, token, "GET", "work", params={"content": 0})
            if dir_resp.status_code == 404:
                main._user_contents_request(user, token, "PUT", "work", json={"type": "directory"})

            exists_resp = main._user_contents_request(user, token, "GET", notebook_relpath, params={"content": 0})
            if exists_resp.status_code == 404:
                notebook_json = None
                template_path = main._normalize_text(target_experiment.notebook_path or "")
                if template_path:
                    tpl_resp = main._user_contents_request(
                        user, token, "GET", template_path, params={"content": 1}
                    )
                    if tpl_resp.status_code == 200:
                        tpl_payload = tpl_resp.json() or {}
                        if tpl_payload.get("type") == "notebook" and tpl_payload.get("content"):
                            notebook_json = tpl_payload.get("content")

                if notebook_json is None:
                    notebook_json = main._empty_notebook_json()

                put_resp = main._user_contents_request(
                    user,
                    token,
                    "PUT",
                    notebook_relpath,
                    json={"type": "notebook", "format": "json", "content": notebook_json},
                )
                if put_resp.status_code not in {200, 201}:
                    print(
                        f"Failed to create notebook via Jupyter API ({put_resp.status_code}): {put_resp.text[:200]}"
                    )
            elif exists_resp.status_code != 200:
                print(
                    f"Failed to access notebook via Jupyter API ({exists_resp.status_code}): {exists_resp.text[:200]}"
                )
        except Exception as exc:
            print(f"JupyterHub auto-login notebook preparation error: {exc}")

    if not token:
        # Fallback path: user may still have a valid Hub cookie from previous visits.
        return {
            "jupyter_url": main._build_user_lab_url(user, path=notebook_relpath),
            "tokenized": False,
            "message": "Failed to mint user token, fell back to non-token URL",
        }

    return {
        "jupyter_url": main._build_user_lab_url(user, path=notebook_relpath, token=token),
        "tokenized": True,
        "message": "ok",
    }


router.add_api_route("/api/jupyterhub/auto-login-url", get_jupyterhub_auto_login_url, methods=["GET"])
