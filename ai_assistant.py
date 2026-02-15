# ai_assistant.py - AI助手服务

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
import httpx
import os
import re

app = FastAPI(title="AI编程助手")

# ==================== 配置 ====================

# 选择AI后端
AI_BACKEND = os.getenv("AI_BACKEND", "ollama")  # ollama / openai / local

# Ollama配置（本地部署）
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "codellama:7b")

# OpenAI配置（云服务）
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4")

# ==================== 数据模型 ====================

class CodeReviewRequest(BaseModel):
    code: str
    language: str = "python"
    check_style: bool = True
    check_security: bool = True

class CodeReviewResponse(BaseModel):
    issues: List[Dict]
    suggestions: List[str]
    score: float
    summary: str

class ExplainCodeRequest(BaseModel):
    code: str
    language: str = "python"
    detail_level: str = "medium"  # brief / medium / detailed

class DebugRequest(BaseModel):
    code: str
    error_message: str
    language: str = "python"

class ChatRequest(BaseModel):
    message: str
    context: Optional[str] = None
    history: Optional[List[Dict]] = None

# ==================== AI后端接口 ====================

class AIBackend:
    """AI后端抽象类"""
    
    async def chat_completion(self, messages: List[Dict]) -> str:
        raise NotImplementedError

class OllamaBackend(AIBackend):
    """Ollama本地模型后端"""
    
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url
        self.model = model
    
    async def chat_completion(self, messages: List[Dict]) -> str:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": False
                    },
                    timeout=60.0
                )
                response.raise_for_status()
                return response.json()["message"]["content"]
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Ollama错误: {str(e)}")

class OpenAIBackend(AIBackend):
    """OpenAI API后端"""
    
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
    
    async def chat_completion(self, messages: List[Dict]) -> str:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": messages
                    },
                    timeout=60.0
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"OpenAI错误: {str(e)}")

# 初始化AI后端
def get_ai_backend() -> AIBackend:
    if AI_BACKEND == "ollama":
        return OllamaBackend(OLLAMA_BASE_URL, OLLAMA_MODEL)
    elif AI_BACKEND == "openai":
        return OpenAIBackend(OPENAI_API_KEY, OPENAI_MODEL)
    else:
        raise ValueError(f"不支持的AI后端: {AI_BACKEND}")

ai_backend = get_ai_backend()

# ==================== 提示词模板 ====================

CODE_REVIEW_PROMPT = """你是一个专业的代码审查专家。请审查以下{language}代码，并提供：
1. 代码质量评分（0-100）
2. 发现的问题（包括行号、类型、描述）
3. 改进建议
4. 总体评价

请以JSON格式返回结果。

代码：
```{language}
{code}
```

返回格式示例：
{{
    "score": 85,
    "issues": [
        {{"line": 5, "type": "warning", "message": "变量命名不规范"}},
        {{"line": 12, "type": "error", "message": "缺少异常处理"}}
    ],
    "suggestions": [
        "建议使用类型注解",
        "考虑使用列表推导式"
    ],
    "summary": "代码整体质量良好，但需要注意..."
}}
"""

EXPLAIN_CODE_PROMPT = """请解释以下{language}代码的功能和实现逻辑。

详细程度：{detail_level}
- brief: 简要说明代码功能
- medium: 解释主要逻辑和关键步骤
- detailed: 详细解释每个部分和技术细节

代码：
```{language}
{code}
```

请用清晰、易懂的语言解释，适合学习者理解。
"""

DEBUG_PROMPT = """你是一个调试专家。学生遇到了以下错误，请帮助分析和解决。

代码：
```{language}
{code}
```

错误信息：
```
{error_message}
```

请提供：
1. 错误原因分析
2. 可能的解决方案（至少2个）
3. 预防类似错误的建议
4. 修复后的代码示例

请用教学的口吻，帮助学生理解问题。
"""

CHAT_PROMPT = """你是一个友好的编程学习助手。学生向你提问：

{message}

{context_section}

请提供清晰、准确的回答，并：
1. 使用简单易懂的语言
2. 提供代码示例（如果相关）
3. 给出延伸学习的建议
4. 保持鼓励和支持的态度
"""

# ==================== API端点 ====================

@app.get("/")
def root():
    return {
        "service": "AI编程助手",
        "backend": AI_BACKEND,
        "model": OLLAMA_MODEL if AI_BACKEND == "ollama" else OPENAI_MODEL,
        "status": "running"
    }

@app.post("/api/code-review", response_model=CodeReviewResponse)
async def code_review(request: CodeReviewRequest):
    """AI代码审查"""
    
    prompt = CODE_REVIEW_PROMPT.format(
        language=request.language,
        code=request.code
    )
    
    messages = [
        {"role": "system", "content": "你是一个专业的代码审查专家。"},
        {"role": "user", "content": prompt}
    ]
    
    try:
        response = await ai_backend.chat_completion(messages)
        
        # 解析JSON响应
        import json
        # 尝试提取JSON部分
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            # 如果无法解析，返回默认结构
            result = {
                "score": 70,
                "issues": [],
                "suggestions": [response],
                "summary": "AI审查完成"
            }
        
        return CodeReviewResponse(**result)
    
    except Exception as e:
        # 降级处理：使用静态分析
        return fallback_code_review(request.code, request.language)

@app.post("/api/explain-code")
async def explain_code(request: ExplainCodeRequest):
    """AI代码解释"""
    
    prompt = EXPLAIN_CODE_PROMPT.format(
        language=request.language,
        code=request.code,
        detail_level=request.detail_level
    )
    
    messages = [
        {"role": "system", "content": "你是一个优秀的编程教师。"},
        {"role": "user", "content": prompt}
    ]
    
    explanation = await ai_backend.chat_completion(messages)
    
    return {
        "explanation": explanation,
        "code_length": len(request.code),
        "language": request.language
    }

@app.post("/api/debug-help")
async def debug_help(request: DebugRequest):
    """AI调试帮助"""
    
    prompt = DEBUG_PROMPT.format(
        language=request.language,
        code=request.code,
        error_message=request.error_message
    )
    
    messages = [
        {"role": "system", "content": "你是一个耐心的调试专家和教师。"},
        {"role": "user", "content": prompt}
    ]
    
    help_text = await ai_backend.chat_completion(messages)
    
    return {
        "help": help_text,
        "error_type": extract_error_type(request.error_message),
        "language": request.language
    }

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """AI对话助手"""
    
    context_section = ""
    if request.context:
        context_section = f"\n上下文信息：\n{request.context}\n"
    
    prompt = CHAT_PROMPT.format(
        message=request.message,
        context_section=context_section
    )
    
    # 构建消息历史
    messages = [
        {"role": "system", "content": "你是一个友好、耐心的编程学习助手。"}
    ]
    
    if request.history:
        messages.extend(request.history)
    
    messages.append({"role": "user", "content": prompt})
    
    response = await ai_backend.chat_completion(messages)
    
    return {
        "answer": response,
        "conversation_id": None  # 可以实现会话管理
    }

@app.post("/api/generate-test-cases")
async def generate_test_cases(code: str, language: str = "python"):
    """生成测试用例"""
    
    prompt = f"""为以下{language}代码生成完整的单元测试用例：

```{language}
{code}
```

请生成：
1. 正常情况测试
2. 边界条件测试
3. 异常情况测试

使用pytest框架编写测试代码。
"""
    
    messages = [
        {"role": "system", "content": "你是一个测试专家。"},
        {"role": "user", "content": prompt}
    ]
    
    test_code = await ai_backend.chat_completion(messages)
    
    return {
        "test_code": test_code,
        "framework": "pytest"
    }

@app.post("/api/optimize-code")
async def optimize_code(code: str, language: str = "python"):
    """代码优化建议"""
    
    prompt = f"""请优化以下{language}代码，提供：
1. 性能优化建议
2. 代码可读性改进
3. 优化后的代码
4. 性能对比说明

原代码：
```{language}
{code}
```
"""
    
    messages = [
        {"role": "system", "content": "你是一个代码优化专家。"},
        {"role": "user", "content": prompt}
    ]
    
    optimization = await ai_backend.chat_completion(messages)
    
    return {
        "optimization": optimization,
        "original_code": code
    }

# ==================== 辅助函数 ====================

def fallback_code_review(code: str, language: str) -> CodeReviewResponse:
    """降级代码审查（当AI不可用时）"""
    issues = []
    suggestions = []
    
    # 简单的静态检查
    lines = code.split('\n')
    
    for i, line in enumerate(lines, 1):
        # 检查行长度
        if len(line) > 100:
            issues.append({
                "line": i,
                "type": "warning",
                "message": "行过长，建议不超过100字符"
            })
        
        # 检查变量命名（简单示例）
        if language == "python" and re.search(r'\b[a-z]\b\s*=', line):
            issues.append({
                "line": i,
                "type": "info",
                "message": "考虑使用更有意义的变量名"
            })
    
    if not issues:
        suggestions.append("代码格式良好")
    
    score = max(50, 100 - len(issues) * 5)
    
    return CodeReviewResponse(
        issues=issues,
        suggestions=suggestions,
        score=score,
        summary=f"静态分析完成，发现{len(issues)}个问题"
    )

def extract_error_type(error_message: str) -> str:
    """从错误信息中提取错误类型"""
    common_errors = {
        "NameError": "变量未定义",
        "TypeError": "类型错误",
        "ValueError": "值错误",
        "IndexError": "索引越界",
        "KeyError": "键不存在",
        "AttributeError": "属性不存在",
        "SyntaxError": "语法错误",
        "IndentationError": "缩进错误"
    }
    
    for error_type, description in common_errors.items():
        if error_type in error_message:
            return description
    
    return "未知错误"

# ==================== 健康检查 ====================

@app.get("/health")
async def health_check():
    """健康检查"""
    try:
        # 测试AI后端连接
        test_messages = [{"role": "user", "content": "测试"}]
        await ai_backend.chat_completion(test_messages)
        return {"status": "healthy", "backend": AI_BACKEND}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    print(f"启动AI助手服务 - 使用后端: {AI_BACKEND}")
    uvicorn.run(app, host="0.0.0.0", port=8002)
