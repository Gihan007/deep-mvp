# path: src/app/routes/update_graph_router.py

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import time
import uuid
from langchain_community.callbacks import get_openai_callback
import logging
import traceback
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Pydantic models for request/response
class GraphUpdateRequest(BaseModel):
    question: str
    session_id: Optional[str] = None

class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    total_cost: float

class GraphUpdateResponse(BaseModel):
    answer: str
    success: bool
    execution_time: str
    token_usage: TokenUsage
    source: Optional[List[dict]] = None

def get_app(request: Request):
    return request.app


@router.post("/api/update_graph/execute", response_model=GraphUpdateResponse)
def execute_graph_update(request_data: GraphUpdateRequest, app = Depends(get_app)):
    """
    Execute graph database updates using the CS_ChatQABot (GRAPH_UPDATE_GRAPH.py).
    This endpoint handles CREATE, UPDATE, DELETE, MERGE operations on Neo4j.
    """
    # Record start time
    start_time = time.time()
    
    # Set default session_id if not provided
    session_id = request_data.session_id or f"update_session_{uuid.uuid4().hex[:8]}"
    
    try:
        # Check if update_chatbot exists
        if not hasattr(app, 'update_chatbot'):
            raise HTTPException(
                status_code=500,
                detail="Graph update bot not initialized. Check app initialization."
            )
        
        logger.info(f"[UPDATE GRAPH] Session: {session_id}, Question: {request_data.question}")
        
        # Execute bot with OpenAI callback to track token usage
        with get_openai_callback() as cb:
            response = app.update_chatbot.run({
                "question": request_data.question,
                "session_id": session_id,
            })
        
        # Create token usage summary
        token_usage = TokenUsage(
            prompt_tokens=cb.prompt_tokens,
            completion_tokens=cb.completion_tokens,
            total_tokens=cb.total_tokens,
            total_cost=cb.total_cost
        )
        
        # Extract answer text
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
            logger.warning("Empty answer_text from update_chatbot; using fallback message.")
            answer_text = "I'm sorry, I couldn't execute the graph update operation."

        # Get source details
        source_details = response.get("source_details") or response.get("source")

        logger.info(f"[UPDATE GRAPH] Response: {answer_text}")
        if source_details:
            logger.info(f"[UPDATE GRAPH] Source: {source_details}")
        
        execution_time = time.time() - start_time
        
        return GraphUpdateResponse(
            answer=answer_text,
            success=True,
            execution_time=f"{execution_time:.2f} seconds",
            token_usage=token_usage,
            source=source_details
        )
    
    except Exception as e:
        # Calculate execution time even on error
        execution_time = time.time() - start_time
        error_traceback = traceback.format_exc()

        logger.error(f"Graph update failed: {str(e)}")
        logger.error(f"Traceback:\n{error_traceback}")
        logger.error(f"=== Graph Update Request Failed after {execution_time:.2f} seconds ===")
                
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Failed to execute graph update: {str(e)}",
                "success": False,
                "session_id": session_id,
                "execution_time": f"{execution_time:.2f} seconds",
            }
        )





@router.post("/api/update_graph/stream")
async def stream_graph_update(request_data: GraphUpdateRequest, request: Request, app = Depends(get_app)):
    """
    Server-Sent Events endpoint for streaming graph update operations token-by-token.
    Emits SSE events:
      - event: session  data: {"session_id": "..."}
      - event: token    data: {"type": "token", "agent": "agent_name", "role": "assistant", "content": "..."}
      - event: done     data: {"type": "done", "session_id": "..."}
      - event: error    data: {"type": "error", "error": "...", "session_id": "..."}
    """
    # Session
    session_id = request_data.session_id or f"update_session_{uuid.uuid4().hex[:8]}"

    try:
        # Check if update_chatbot exists
        if not hasattr(app, 'update_chatbot'):
            raise HTTPException(
                status_code=500,
                detail="Graph update bot not initialized. Check app initialization."
            )

        async def event_gen():
            # Immediately send session info
            yield f"event: session\n"
            yield f"data: {json.dumps({'session_id': session_id})}\n\n"

            try:
                # Drive the graph streaming generator
                async for event in app.update_chatbot.stream({
                    "question": request_data.question,
                    "session_id": session_id,
                }):
                    evt_type = event.get("type", "token")
                    payload = json.dumps(event, ensure_ascii=False)
                    yield f"event: {evt_type}\n"
                    yield f"data: {payload}\n\n"

            except asyncio.CancelledError:
                logger.info(f"[UPDATE GRAPH STREAM] Client disconnected for session {session_id}")
                raise
            except Exception as e:
                err = {"type": "error", "error": str(e), "session_id": session_id}
                yield "event: error\n"
                yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"

        # Stream as SSE
        headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
        return StreamingResponse(event_gen(), media_type="text/event-stream", headers=headers)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Failed to start streaming graph update: {str(e)}",
                "success": False,
                "session_id": session_id,
            }
        )
