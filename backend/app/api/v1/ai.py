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

async def get_ai_shared_config(username: str, request: Request):
    normalized_user = _normalize_text(username)
    if not normalized_user:
        raise HTTPException(status_code=400, detail="username不能为空")
    if not _is_known_user(normalized_user):
        raise HTTPException(status_code=404, detail="用户不存在")
    _require_ai_session(request, expected_username=normalized_user, allow_admin_override=True)
    return _build_ai_shared_config_response(include_secrets=False)

async def update_ai_shared_config(payload: AISharedConfigUpdateRequest, request: Request):
    teacher_username = _normalize_text(payload.teacher_username)
    _require_ai_session(request, expected_username=teacher_username, allow_admin_override=True)
    _ensure_teacher(teacher_username)

    updated = _normalize_ai_shared_config(payload.dict())
    ai_shared_config_db.update(updated)
    _save_ai_shared_config()
    return _build_ai_shared_config_response(include_secrets=False)

async def get_ai_chat_history(username: str, request: Request):
    normalized_user = _normalize_text(username)
    if not normalized_user:
        raise HTTPException(status_code=400, detail="username不能为空")
    if not _is_known_user(normalized_user):
        raise HTTPException(status_code=404, detail="用户不存在")
    _require_ai_session(request, expected_username=normalized_user, allow_admin_override=True)

    messages = _get_ai_chat_history(normalized_user)
    return AIChatHistoryResponse(
        username=normalized_user,
        message_count=len(messages),
        messages=[AIChatHistoryMessage(**item) for item in messages],
    )

async def update_ai_chat_history(payload: AIChatHistoryUpdateRequest, request: Request):
    normalized_user = _normalize_text(payload.username)
    if not normalized_user:
        raise HTTPException(status_code=400, detail="username不能为空")
    if not _is_known_user(normalized_user):
        raise HTTPException(status_code=404, detail="用户不存在")
    _require_ai_session(request, expected_username=normalized_user, allow_admin_override=True)

    raw_messages = [{"role": item.role, "content": item.content} for item in payload.messages]
    saved = _set_ai_chat_history(normalized_user, raw_messages)
    return AIChatHistoryResponse(
        username=normalized_user,
        message_count=len(saved),
        messages=[AIChatHistoryMessage(**item) for item in saved],
    )

async def ai_network_time(request: Request):
    _require_ai_session(request)
    system_now = datetime.now().astimezone()
    network_time, errors = _fetch_network_time()
    return {
        "network_available": bool(network_time),
        "network_time": network_time,
        "system_time": {
            "local_iso": system_now.isoformat(),
            "local_readable": system_now.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "utc_iso": system_now.astimezone(timezone.utc).isoformat(),
        },
        "errors": errors[:3],
    }

async def ai_web_search(payload: AIWebSearchRequest, request: Request):
    _require_ai_session(request)
    return _run_web_search(payload.query, payload.limit)

async def ai_chat_with_search(payload: AIChatWithSearchRequest, request: Request):
    username = _normalize_text(payload.username)
    if not username:
        raise HTTPException(status_code=400, detail="username不能为空")
    if not _is_known_user(username):
        raise HTTPException(status_code=404, detail="用户不存在")
    _require_ai_session(request, expected_username=username, allow_admin_override=True)

    message = _normalize_text(payload.message)
    if not message:
        raise HTTPException(status_code=400, detail="message不能为空")
    is_today_relative = _is_today_relative_query(message)
    is_time_sensitive = _is_time_sensitive_query(message)

    model = _normalize_text(payload.model) or _normalize_text(ai_shared_config_db.get("chat_model")) or DEFAULT_AI_SHARED_CONFIG["chat_model"]
    base_url = _normalize_text(ai_shared_config_db.get("base_url")) or DEFAULT_AI_SHARED_CONFIG["base_url"]
    api_key = _normalize_text(ai_shared_config_db.get("api_key"))
    system_prompt = _normalize_text(ai_shared_config_db.get("system_prompt")) or DEFAULT_AI_SHARED_CONFIG["system_prompt"]
    if not api_key:
        raise HTTPException(status_code=400, detail="AI 配置未保存 API Key，请先在教师端 AI 模块保存配置")

    need_web_search = bool(payload.use_web_search)
    search_decision_reason = "联网模式已关闭"
    if payload.use_web_search and payload.auto_web_search:
        try:
            need_web_search, search_decision_reason = _decide_need_web_search(
                message=message,
                model=model,
                base_url=base_url,
                api_key=api_key,
            )
        except HTTPException:
            need_web_search, search_decision_reason = _fallback_need_web_search_decision(message)
            search_decision_reason = f"AI decision failed, fallback rule used: {search_decision_reason}"
    elif payload.use_web_search:
        search_decision_reason = "联网模式强制开启（跳过 AI 判定）"

    search_provider = ""
    search_resolved_query = ""
    search_cached = False
    search_depth_used = ""
    search_results: List[Dict[str, str]] = []
    search_error = ""
    if need_web_search:
        try:
            search_payload = _run_web_search(message, payload.search_limit)
            search_provider = str(search_payload.get("provider") or "")
            search_resolved_query = str(search_payload.get("resolved_query") or message)
            search_cached = bool(search_payload.get("cached"))
            search_depth_used = str(search_payload.get("search_depth") or "")
            raw_results = search_payload.get("results")
            if isinstance(raw_results, list):
                search_results = [item for item in raw_results if isinstance(item, dict)]
        except HTTPException as exc:
            # Degrade gracefully to plain model answer when network search is unavailable.
            search_error = str(exc.detail)

    search_context = _build_web_search_context(search_results)

    system_parts = [system_prompt, AI_RESPONSE_STYLE_RULES]
    if is_time_sensitive:
        date_tokens = _current_local_date_tokens()
        system_parts.append(
            f"Current server date is {date_tokens['cn']} ({date_tokens['iso']}). "
            "Do not present historical events as if they happened today. "
            "If search results are old, explicitly include the source date."
        )
    if search_context:
        system_parts.append(
            "如果用户消息包含 [WEB_SEARCH_CONTEXT_START]... [WEB_SEARCH_CONTEXT_END]，"
            "必须优先依据这些联网检索内容回答。"
            "回答时在对应句子后使用 [1] [2] 这类编号标注来源，编号对应检索上下文条目。"
            "若没有可用来源，不要编造链接。"
        )
    final_system_prompt = "\n".join(part for part in system_parts if part)

    messages: List[Dict[str, str]] = [{"role": "system", "content": final_system_prompt}]

    raw_history = payload.history if isinstance(payload.history, list) else []
    # “今天/最新”类问题很容易被历史对话中的旧日期污染，默认不带历史。
    trimmed_history = [] if is_today_relative else _trim_ai_history_for_context(raw_history)
    for item in trimmed_history:
        messages.append({
            "role": item.get("role", "user"),
            "content": str(item.get("content") or ""),
        })

    user_content = message
    if search_context:
        user_content = f"{message}\n\n{search_context}"
    messages.append({"role": "user", "content": user_content})

    answer = _call_ai_chat_model(
        model=model,
        messages=messages,
        base_url=base_url,
        api_key=api_key,
    )

    return {
        "answer": answer,
        "model": model,
        "search_decision": {
            "need_web_search": bool(need_web_search),
            "reason": search_decision_reason,
        },
        "search_provider": search_provider,
        "search_resolved_query": search_resolved_query or message,
        "search_cached": search_cached,
        "search_depth": search_depth_used,
        "search_results": search_results[:8],
        "search_error": search_error,
    }

async def ai_code_review(code: str, language: str = "python"):
    """AI代码审查"""
    # 这里集成 AI 模型进行代码审查
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

async def ai_explain_code(code: str):
    """AI代码解释"""
    return {
        "explanation": "这段代码实现了...",
        "key_concepts": ["循环", "条件判断", "列表操作"],
        "complexity": "O(n)"
    }

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

async def ai_chat(question: str, context: Optional[str] = None):
    """AI问答助手"""
    return {
        "answer": "根据你的问题...",
        "related_topics": ["Python基础", "数据结构"],
        "references": ["官方文档链接"]
    }

router.add_api_route("/api/ai/config", get_ai_shared_config, methods=["GET"], response_model=main.AISharedConfigResponse)
router.add_api_route("/api/ai/config", update_ai_shared_config, methods=["PUT"], response_model=main.AISharedConfigResponse)
router.add_api_route("/api/ai/chat-history", get_ai_chat_history, methods=["GET"], response_model=main.AIChatHistoryResponse)
router.add_api_route("/api/ai/chat-history", update_ai_chat_history, methods=["PUT"], response_model=main.AIChatHistoryResponse)
router.add_api_route("/api/ai/network-time", ai_network_time, methods=["GET"])
router.add_api_route("/api/ai/web-search", ai_web_search, methods=["POST"])
router.add_api_route("/api/ai/chat-with-search", ai_chat_with_search, methods=["POST"])
router.add_api_route("/api/ai/code-review", ai_code_review, methods=["POST"])
router.add_api_route("/api/ai/explain-code", ai_explain_code, methods=["POST"])
router.add_api_route("/api/ai/debug-help", ai_debug_help, methods=["POST"])
router.add_api_route("/api/ai/chat", ai_chat, methods=["POST"])
