from fastapi import APIRouter


def _get_main_module():
    from ... import main
    return main


main = _get_main_module()


def _bind_main_symbols():
    for name in dir(main):
        if name.startswith("__"):
            continue
        globals().setdefault(name, getattr(main, name))


_bind_main_symbols()
router = APIRouter()

async def upload_attachments(
    experiment_id: str,
    files: List[UploadFile] = File(...)
):
    """上传附件"""
    if experiment_id not in experiments_db:
        raise HTTPException(status_code=404, detail="实验不存在")
    
    uploaded_files = []
    
    for file in files:
        # Generate unique ID and filename
        att_id = str(uuid.uuid4())
        # Prevent filename collision
        safe_filename = file.filename.replace(" ", "_")
        file_path = os.path.join(UPLOAD_DIR, f"{att_id}_{safe_filename}")
        
        # Save to disk
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            print(f"Error saving file {file.filename}: {e}")
            continue
            
        # Create metadata
        attachment = Attachment(
            id=att_id,
            experiment_id=experiment_id,
            filename=file.filename,
            file_path=file_path,
            content_type=file.content_type or "application/octet-stream",
            size=os.path.getsize(file_path),
            created_at=datetime.now()
        )
        
        attachments_db[att_id] = attachment
        uploaded_files.append(attachment)
    
    if uploaded_files:
        _save_attachment_registry()

    return uploaded_files

async def list_attachments(experiment_id: str):
    """获取实验附件列表"""
    return [
        att for att in attachments_db.values()
        if att.experiment_id == experiment_id
    ]

async def download_attachment(attachment_id: str):
    """下载附件"""
    if attachment_id not in attachments_db:
        raise HTTPException(status_code=404, detail="附件不存在")
    
    att = attachments_db[attachment_id]
    if not os.path.exists(att.file_path):
        raise HTTPException(status_code=404, detail="文件物理路径不存在")
        
    lower_filename = att.filename.lower()
    is_pdf = att.content_type == "application/pdf" or lower_filename.endswith(".pdf")
    is_ppt = (
        att.content_type in [
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ]
        or lower_filename.endswith(".ppt")
        or lower_filename.endswith(".pptx")
    )
    content_disposition = "inline" if (is_pdf or is_ppt) else "attachment"
    
    # Ensure Content-Type is correct for common preview file types
    if is_pdf:
        media_type = "application/pdf"
    elif lower_filename.endswith(".pptx"):
        media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    elif lower_filename.endswith(".ppt"):
        media_type = "application/vnd.ms-powerpoint"
    else:
        media_type = att.content_type
    
    # Use ASCII filename for inline display to prevent header encoding issues in some browsers
    response_filename = "document.pdf" if is_pdf else att.filename
    
    return FileResponse(
        path=att.file_path,
        filename=response_filename,
        media_type=media_type,
        content_disposition_type=content_disposition
    )

async def download_attachment_word(attachment_id: str):
    """Prefer Word attachment for download; fallback to original attachment."""
    if attachment_id not in attachments_db:
        raise HTTPException(status_code=404, detail="attachment not found")

    att = attachments_db[attachment_id]
    if not os.path.exists(att.file_path):
        raise HTTPException(status_code=404, detail="attachment file not found")

    target_attachment = att
    if _is_pdf_attachment(att):
        paired_word = _find_paired_word_attachment(att)
        if paired_word is not None:
            target_attachment = paired_word

    lower_filename = target_attachment.filename.lower()
    if lower_filename.endswith(".docx"):
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif lower_filename.endswith(".doc"):
        media_type = "application/msword"
    elif lower_filename.endswith(".pdf"):
        media_type = "application/pdf"
    elif lower_filename.endswith(".pptx"):
        media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    elif lower_filename.endswith(".ppt"):
        media_type = "application/vnd.ms-powerpoint"
    else:
        media_type = target_attachment.content_type or "application/octet-stream"

    return FileResponse(
        path=target_attachment.file_path,
        filename=target_attachment.filename,
        media_type=media_type,
        content_disposition_type="attachment",
    )

router.add_api_route("/api/teacher/experiments/{experiment_id}/attachments", upload_attachments, methods=["POST"])
router.add_api_route("/api/experiments/{experiment_id}/attachments", list_attachments, methods=["GET"], response_model=list[main.Attachment])
router.add_api_route("/api/attachments/{attachment_id}/download", download_attachment, methods=["GET"])
router.add_api_route("/api/attachments/{attachment_id}/download-word", download_attachment_word, methods=["GET"])
