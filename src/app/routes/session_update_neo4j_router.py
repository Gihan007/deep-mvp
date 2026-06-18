# path: src/app/routes/session_routes.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from config import get_config
import time
from app.utills.session_manager import SessionManager
from langchain_community.callbacks import get_openai_callback
import json
import logging
import traceback
from config import Config


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router

db_path = Config.SESSION_UPDATE_NEO4J_DATABASE_PATH


router = APIRouter()
session_manager = SessionManager(db_path)

# Pydantic models
class SessionDetail(BaseModel):
    session_id: str
    message_count: int
    error: Optional[str] = None

class SessionsResponse(BaseModel):
    sessions: List[SessionDetail]
    total_count: int

class SessionResponse(BaseModel):
    session_id: str
    history: Dict[str, Any]
    message_count: int

class DeleteResponse(BaseModel):
    message: str
    session_id: Optional[str] = None
    deleted_count: Optional[int] = None





@router.get("/api/sessions_update_neo4j", response_model=SessionsResponse)
def list_sessions():
    """Get all available sessions."""
    try:
        sessions = session_manager.list_all_sessions()
        
        # Get detailed info for each session
        session_details = []
        for session_id in sessions:
            try:
                session_data = session_manager.get_session_data(session_id)
                session_details.append(SessionDetail(
                    session_id=session_id,
                    message_count=len(session_data['messages'])
                ))
            except Exception as e:
                logger.warning(f"Failed to get info for session {session_id}: {e}")
                traceback.print_exc()
                session_details.append(SessionDetail(
                    session_id=session_id,
                    message_count=0,
                    error="Failed to get session info"
                ))
        
        return SessionsResponse(
            sessions=session_details,
            total_count=len(sessions)
        )
        
    except Exception as e:
        logger.error(f"Error listing sessions: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list sessions: {str(e)}"
        )




@router.get("/api/sessions_update_neo4j/{session_id}", response_model=SessionResponse)
def get_session(session_id: str):
    """Get session history and info. If the session doesn't exist yet, return an empty history instead of 404."""
    try:
        history = session_manager.get_session_data(session_id)

        # history is a dict like {'session_id': id, 'messages': [...], 'exists': bool}
        if not history or not history.get('exists', False):
            empty_history = {
                "session_id": session_id,
                "messages": [],
                "exists": False,
            }
            return SessionResponse(
                session_id=session_id,
                history=empty_history,
                message_count=0,
            )

        return SessionResponse(
            session_id=session_id,
            history=history,
            message_count=len(history.get('messages', []))
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session {session_id}: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get session: {str(e)}"
        )



@router.delete("/api/sessions_update_neo4j/{session_id}", response_model=DeleteResponse)
def delete_session(session_id: str):
    """Delete a specific session."""
    try:
        success = session_manager.delete_session_data(session_id)
        
        if success:
            return DeleteResponse(
                message=f"Session {session_id} deleted successfully",
                session_id=session_id
            )
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session {session_id}: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete session: {str(e)}"
        )




@router.delete("/api/sessions_update_neo4j", response_model=DeleteResponse)
def clear_all_sessions():
    """Clear all sessions."""
    try:
        count = session_manager.delete_all_sessions()
        
        return DeleteResponse(
            message=f"Successfully deleted {count} sessions",
            deleted_count=count
        )
        
    except Exception as e:
        logger.error(f"Error clearing all sessions: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear sessions: {str(e)}"
        )

# Backward-compat routes for original typo path
@router.delete("/api/sessions_upate_neo4j/{session_id}", response_model=DeleteResponse)
def delete_session_compat(session_id: str):
    return delete_session(session_id)

@router.delete("/api/sessions_upate_neo4j", response_model=DeleteResponse)
def clear_all_sessions_compat():
    return clear_all_sessions()
