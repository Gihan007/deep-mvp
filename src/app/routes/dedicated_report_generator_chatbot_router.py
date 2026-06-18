# path: src/app/routes/chatbot_routes.py

from fastapi import APIRouter, Request, HTTPException, Depends
from openai import NotFoundError as OpenAINotFoundError
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
import asyncio
import time
import uuid
from langchain_community.callbacks import get_openai_callback
import logging
import traceback
import base64
import tempfile
import mimetypes
import shutil
import os
import json
from app.utills.data_inject_chroma_db import user_data_store
from typing import Optional, List, Dict, Any


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Helper utilities for base64 decoding and temp file handling
def _split_data_url(b64_str: str):
    try:
        if b64_str and b64_str.startswith("data:") and "," in b64_str:
            header, data = b64_str.split(",", 1)
            mime = header[5:].split(";")[0] or None
            return mime, data
    except Exception:
        pass
    return None, b64_str

def _guess_ext(mime: Optional[str], default_ext: str = ".bin") -> str:
    if not mime:
        return default_ext
    ext = mimetypes.guess_extension(mime) or default_ext
    if ext == ".jpe":
        ext = ".jpg"
    return ext

def _detect_ext_from_bytes(data: bytes, default_ext: str = ".bin") -> str:
    """
    Best-effort file type detection using magic numbers and lightweight heuristics.
    Targets common types: jpg, png, gif, webp, pdf, wav, mp3, ogg, json, csv, txt.
    """
    try:
        # Images
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return ".png"
        if data.startswith(b"\xff\xd8\xff"):
            return ".jpg"
        if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
            return ".gif"
        if len(data) >= 12 and data[0:4] == b"RIFF" and data[8:12] == b"WEBP":
            return ".webp"
        # Documents
        if data.startswith(b"%PDF-"):
            return ".pdf"
        # Audio
        if len(data) >= 12 and data[0:4] == b"RIFF" and data[8:12] == b"WAVE":
            return ".wav"
        if data[0:3] == b"ID3" or (len(data) > 1 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
            return ".mp3"
        if data.startswith(b"OggS"):
            return ".ogg"
        # Text detection
        try:
            text = data.decode("utf-8")
            s = text.strip()
            try:
                json.loads(s)
                return ".json"
            except Exception:
                pass
            if "," in s and "\n" in s and "{" not in s and "}" not in s:
                return ".csv"
            return ".txt"
        except UnicodeDecodeError:
            return default_ext
    except Exception:
        return default_ext



def _save_base64_list(b64_list: Optional[List[str]], base_dir: str, subdir: str, default_ext: str) -> List[str]:
    """
    Persist a list of base64 items to disk, deriving the correct extension from either:
    - Data URL MIME type header (preferred), or
    - File signature/magic-number/text heuristics when no MIME header is present.
    """
    paths: List[str] = []
    if not b64_list:
        return paths
    target_dir = os.path.join(base_dir, subdir)
    os.makedirs(target_dir, exist_ok=True)
    for item in b64_list:
        if not item:
            continue
        mime, payload = _split_data_url(item)
        try:
            binary = base64.b64decode(payload, validate=True)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid base64 content for {subdir}: {str(e)}")
        # Prefer MIME from data URL; otherwise detect from bytes
        if mime:
            ext = _guess_ext(mime, default_ext)
        else:
            ext = _detect_ext_from_bytes(binary, default_ext)
        fname = f"{uuid.uuid4().hex}{ext.lower()}"
        fpath = os.path.join(target_dir, fname)
        with open(fpath, "wb") as f:
            f.write(binary)
        paths.append(fpath)
    return paths

# Create router
router = APIRouter()

# Pydantic models for request/response
class ChatQARequest(BaseModel):
    # High-level report generation inputs
    report_type: Optional[str] = None
    time_horizon: Optional[str] = "last 5 years"
    ticker: Optional[str] = None
    company_name: Optional[str] = None
    industry_name: Optional[str] = None
    instructions: Optional[str] = None
    session_id: Optional[str] = None


class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    total_cost: float

class ChatQAResponse(BaseModel):
    answer: str
    success: bool
    execution_time: str
    token_usage: TokenUsage
    source: Optional[List[dict]] = None
    base64_images: Optional[List[Dict[str, Any]]] = None
    report_base64: Optional[str] = None

def get_app(request: Request):
    return request.app



@router.post("/api/deep_qa_bot_report", response_model=ChatQAResponse)
def get_chat_qa(request_data: ChatQARequest, app = Depends(get_app)):
    # Record start time
    start_time = time.time()
    
    # Set default session_id if not provided
    session_id = request_data.session_id or f"session_{uuid.uuid4().hex[:8]}"

    temp_dir = None
    
    try:
        # Create temp directory and persist base64 inputs to files
        # temp_dir = tempfile.mkdtemp(prefix="chatbot_uploads_")
        # path_images = _save_base64_list(request_data.base64_images, temp_dir, "images", ".png")     # png,jpeg,jpg
        # print("path_images:", path_images)
        # path_files = _save_base64_list(request_data.base64_files, temp_dir, "files", ".bin")      # txt , PDF, Json, CSV
        # print("path_files:", path_files)
        # path_audios = _save_base64_list(request_data.base64_audios, temp_dir, "audios", ".wav")
        # print("path_audios:", path_audios)

        # user_data_store(path_images, path_files, path_audios, session_id, request_data.question, app.embeddings, app.llm)

        # Execute bot with OpenAI callback to track token usage
        with get_openai_callback() as cb:
            response = app.dedicated_report_generator_chatbot.run({
                "instructions": request_data.instructions,
                "session_id": request_data.session_id,
                "report_type": request_data.report_type,
                "time_horizon": request_data.time_horizon,
                "ticker": request_data.ticker,
                "company_name": request_data.company_name,
                "industry_name": request_data.industry_name,
            })
        
        # Create simple token usage summary
        token_usage = TokenUsage(
            prompt_tokens=cb.prompt_tokens,
            completion_tokens=cb.completion_tokens,
            total_tokens=cb.total_tokens,
            total_cost=cb.total_cost
        )
        
        # Normalize and safely extract the answer text regardless of object shape
        raw_answer = response.get("answer", None)

        def _extract_text(msg):
            try:
                content = getattr(msg, "content", msg)
            except Exception:
                content = msg
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict):
                        if "text" in item:
                            parts.append(item["text"])
                    else:
                        parts.append(str(item))
                return "\n".join(parts).strip()
            return str(content) if content is not None else ""

        answer_text = _extract_text(raw_answer)
        if not answer_text or not str(answer_text).strip():
            logger.warning("Empty answer_text from chatbot response; using fallback message.")
            answer_text = "I'm sorry, I couldn't generate a response to this question."

        # Align key names for optional fields, supporting both legacy and new keys
        source_details = response.get("source_details") or response.get("source")
        base64_images = response.get("base64_images")
        report_base64 = response.get("report_base64")

        
        execution_time = time.time() - start_time
        
        return ChatQAResponse(
            answer=answer_text,
            success=True,
            execution_time=f"{execution_time:.2f} seconds",
            token_usage=token_usage,
            source=source_details,
            base64_images=base64_images,
            report_base64= report_base64
        )
    
    except OpenAINotFoundError as e:
        # Typically triggered by invalid/unavailable model name (e.g., REPORT_GENERATION_OPENAI_MODEL)
        execution_time = time.time() - start_time
        logger.error(f"OpenAI model not found/accessible: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "OpenAI model not found or you do not have access to it. Check REPORT_GENERATION_OPENAI_MODEL.",
                "details": str(e),
                "success": False,
                "session_id": session_id,
                "execution_time": f"{execution_time:.2f} seconds",
            },
        )

    except Exception as e:
        # Calculate execution time even on error
        execution_time = time.time() - start_time
        error_traceback = traceback.format_exc()

        logger.error(f"Bot execution failed: {str(e)}")
        logger.error(f"Traceback:\n{error_traceback}")
        logger.error(f"=== QA Bot Request Failed after {execution_time:.2f} seconds ===")
                
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Failed to process question: {str(e)}",
                "success": False,
                "session_id": session_id,
                "execution_time": f"{execution_time:.2f} seconds",
            }
        )
    finally:
        # Cleanup any temp files created for this request
        try:
            if temp_dir and os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as ce:
            logger.warning(f"Temp cleanup failed for {temp_dir}: {ce}")




@router.post("/api/deep_qa_bot_stream_report")
async def stream_chat_qa(request_data: ChatQARequest, request: Request, app = Depends(get_app)):
    """
    Server-Sent Events endpoint that streams AI output token-by-token, including agent metadata.
    Emits SSE events:
      - event: session  data: {"session_id": "..."}
      - event: token    data: {"type": "token", "agent": "agent_name", "role": "assistant|tool|user|system", "content": "..."}
      - event: done     data: {"type": "done", "session_id": "..."}
      - event: error    data: {"type": "error", "error": "...", "session_id": "..."}
    """
    # Session
    session_id = request_data.session_id or f"session_{uuid.uuid4().hex[:8]}"

    # Track execution time for streaming
    start_time = time.time()

    # Prepare temp storage for uploaded base64 payloads
    temp_dir = tempfile.mkdtemp(prefix="chatbot_uploads_stream_")

    try:
        # Persist incoming base64 assets to disk just like non-streaming route
        # path_images = _save_base64_list(request_data.base64_images, temp_dir, "images", ".png")
        # path_files = _save_base64_list(request_data.base64_files, temp_dir, "files", ".bin")
        # path_audios = _save_base64_list(request_data.base64_audios, temp_dir, "audios", ".wav")

        # Optional: store user data into chroma/db for retrieval parity
        # try:
        #     # Prefer question; fallback to instructions for streaming parity
        #     q_text = (request_data.question or request_data.instructions or "")
        #     user_data_store(path_images, path_files, path_audios, session_id, q_text, app.embeddings, app.llm)
        # except Exception as ue:
        #     logger.warning(f"user_data_store failed (continuing): {ue}")

        async def event_gen():
            # Immediately send session info
            yield f"event: session\n"
            yield f"data: {json.dumps({'session_id': session_id})}\n\n"

            try:
                # Drive the graph streaming generator
                async for event in app.dedicated_report_generator_chatbot.stream({
                    # Send both for compatibility; graph can use instructions as in non-stream route
                    "instructions": (request_data.instructions),
                    "session_id": session_id,
                    "report_type": request_data.report_type,
                    "time_horizon": request_data.time_horizon,
                    "ticker": request_data.ticker,
                    "company_name": request_data.company_name,
                    "industry_name": request_data.industry_name,
                }):
                    # Augment final 'done' event with execution_time only
                    try:
                        if event.get("type") == "done":
                            exec_time = time.time() - start_time
                            event["execution_time"] = f"{exec_time:.2f} seconds"
                    except Exception:
                        pass
                    # event is already a simple dict from LS_ChatQABot.stream
                    evt_type = event.get("type", "token")
                    payload = json.dumps(event, ensure_ascii=False)
                    yield f"event: {evt_type}\n"
                    yield f"data: {payload}\n\n"

            except asyncio.CancelledError:
                # Client disconnected
                logger.info(f"SSE client disconnected for session {session_id}")
                raise
            except Exception as e:
                err = {"type": "error", "error": str(e), "session_id": session_id}
                yield "event: error\n"
                yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"
            finally:
                # Cleanup temp files created for this stream
                try:
                    if temp_dir and os.path.isdir(temp_dir):
                        shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception as ce:
                    logger.warning(f"Temp cleanup failed for {temp_dir}: {ce}")

        # Stream as SSE
        headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
        return StreamingResponse(event_gen(), media_type="text/event-stream", headers=headers)

    except HTTPException:
        # Pass-through HTTP exceptions
        raise
    except Exception as e:
        # If an error occurs before we start streaming, cleanup and return JSON error
        try:
            if temp_dir and os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as ce:
            logger.warning(f"Temp cleanup failed for {temp_dir}: {ce}")

        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Failed to start streaming: {str(e)}",
                "success": False,
                "session_id": session_id,
            }
        )
