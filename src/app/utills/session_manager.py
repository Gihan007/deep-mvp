from typing import List, Dict, Optional
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.base import BaseCheckpointSaver
from typing import List, Dict, Any, Optional, Iterator
import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3
import traceback
#from flask import current_app
from config import Config


class SessionManager:
    """
    A standalone session management class for handling chat sessions stored in SQLite.
    This class provides methods to manage conversation sessions independently of the main ChatQABot.
    """
    
    def __init__(self, db_path):
        """
        Initialize the SessionManager with a database path.
        Args:
            db_path (str): Path to the SQLite database file
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.checkpointer = SqliteSaver(self.conn)




    def get_session_data(self, session_id: str, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Retrieve checkpoint data for a specific session using LangGraph's checkpointer.
        Filters to show only human messages and the final AI response for each turn.
        """
        try:
            config = {"configurable": {"thread_id": session_id}}
            try:
                checkpoints = list(self.checkpointer.list(config, limit=limit))
            except sqlite3.OperationalError:
                # Database exists but tables are not initialized yet
                print(f"No checkpoint tables found; returning empty for session: {session_id}")
                return {'session_id': session_id, 'messages': [], 'exists': False}
            except Exception as e:
                print(f"Error listing checkpoints for {session_id}: {e}")
                return {'session_id': session_id, 'messages': [], 'exists': False}

            if not checkpoints:
                print(f"No checkpoints found for session: {session_id}")
                return {'session_id': session_id, 'messages': [], 'exists': False}
            
            perticular_checkpoint = checkpoints[0]
            messages = perticular_checkpoint.checkpoint['channel_values']['messages']

            # print("==================")
            # print("ALL messages: ", messages)
            # print("==================")

            # Step 1: Filter out ToolMessages and empty AIMessages
            first_filtered_data = []
            for msg in messages:
                msg_type = type(msg).__name__
                if msg_type == "ToolMessage":
                    continue
                if msg_type == "AIMessage" and not msg.content.strip():
                    continue
                first_filtered_data.append([msg_type, msg.content])

            # Step 2: Keep only HumanMessages and the LAST AIMessage before each HumanMessage
            # (or the last AIMessage if conversation ends with AI response)
            final_filtered_data = []
            
            i = 0
            while i < len(first_filtered_data):
                msg_type, content = first_filtered_data[i]
                
                if msg_type == "HumanMessage":
                    # Extract text content if it's a list (contains media)
                    if isinstance(content, list):
                        text_content = ""
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                text_content = item.get("text", "")
                                break
                        final_filtered_data.append(["HumanMessage", text_content])
                    else:
                        final_filtered_data.append(["HumanMessage", content])
                    
                    # Look ahead to find the last AIMessage before the next HumanMessage
                    j = i + 1
                    last_ai_message = None
                    
                    while j < len(first_filtered_data):
                        next_msg_type, next_content = first_filtered_data[j]
                        
                        if next_msg_type == "HumanMessage":
                            # Found next human message, stop looking
                            break
                        elif next_msg_type == "AIMessage":
                            # Keep track of the latest AI message
                            last_ai_message = ["AIMessage", next_content]
                        
                        j += 1
                    
                    # Add the last AI message found (if any)
                    if last_ai_message:
                        final_filtered_data.append(last_ai_message)
                    
                    i = j  # Skip to the next HumanMessage
                else:
                    i += 1

            # print("==================")
            # print("final_filtered_data: ", final_filtered_data)
            # print("==================")
            
            return {
                'session_id': session_id,
                'messages': final_filtered_data,
                'exists': True
            }

        except Exception as e:
            print(f"Error retrieving session data: {e}")
            return {'session_id': session_id, 'messages': [], 'exists': False}



    def delete_session_data(self, session_id: str) -> bool:
        """
        Delete all checkpoint data for a specific session/thread from the SQLite database.
        Returns:
            True if any deletion occurred, False otherwise.
        """
        try:
            conn = self.checkpointer.conn
            cursor = conn.cursor()

            # Detect available tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('checkpoints','writes')")
            available = {r[0] for r in cursor.fetchall()}
            if not available:
                print("No session tables present; nothing to delete.")
                return False

            deleted_any = False
            if 'checkpoints' in available:
                cursor.execute("""
                    DELETE FROM checkpoints 
                    WHERE thread_id = ?
                """, (session_id,))
                if cursor.rowcount and cursor.rowcount > 0:
                    deleted_any = True
            if 'writes' in available:
                cursor.execute("""
                    DELETE FROM writes 
                    WHERE thread_id = ?
                """, (session_id,))
                if cursor.rowcount and cursor.rowcount > 0:
                    deleted_any = True

            conn.commit()

            if deleted_any:
                print(f"Deleted session data for session: {session_id}")
            else:
                print(f"No data found to delete for session: {session_id}")
            return deleted_any

        except Exception as e:
            print(f"Error deleting session data: {e}")
            traceback.print_exc()
            return False


    def list_all_sessions(self) -> List[str]:
        """
        List all unique session (thread) IDs from the SQLite database.
        Args:
            checkpointer: The LangGraph checkpointer instance (must be SqliteSaver)
        Returns:
            A list of thread_id (session ID) strings.
        """
        try:

            conn = self.checkpointer.conn
            cursor = conn.cursor()

            # Detect available tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('checkpoints','writes')")
            available = {r[0] for r in cursor.fetchall()}
            if not available:
                return []

            if 'checkpoints' in available and 'writes' in available:
                cursor.execute("SELECT DISTINCT thread_id FROM checkpoints UNION SELECT DISTINCT thread_id FROM writes")
            elif 'checkpoints' in available:
                cursor.execute("SELECT DISTINCT thread_id FROM checkpoints")
            else:
                cursor.execute("SELECT DISTINCT thread_id FROM writes")
            rows = cursor.fetchall()

            session_ids = [row[0] for row in rows]
            print(f"Found {len(session_ids)} session(s): {session_ids}")
            return session_ids

        except Exception as e:
            print(f"Error listing session IDs: {e}")
            traceback.print_exc()
            return []



    def delete_all_sessions(self) -> int:
        """
        Delete all session checkpoint data from the SQLite database.
        Returns:
            The number of distinct sessions deleted across all session tables.
        """
        try:
            conn = self.checkpointer.conn
            cursor = conn.cursor()

            # Detect available tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('checkpoints','writes')")
            available = {r[0] for r in cursor.fetchall()}
            if not available:
                return 0

            # Count distinct sessions before deletion across available tables
            if 'checkpoints' in available and 'writes' in available:
                cursor.execute("SELECT COUNT(DISTINCT thread_id) FROM (SELECT thread_id FROM checkpoints UNION SELECT thread_id FROM writes)")
            elif 'checkpoints' in available:
                cursor.execute("SELECT COUNT(DISTINCT thread_id) FROM checkpoints")
            else:
                cursor.execute("SELECT COUNT(DISTINCT thread_id) FROM writes")
            row = cursor.fetchone()
            deleted_sessions = int(row[0]) if row and row[0] is not None else 0

            # Perform deletion in all available tables
            if 'checkpoints' in available:
                cursor.execute("DELETE FROM checkpoints")
            if 'writes' in available:
                cursor.execute("DELETE FROM writes")
            conn.commit()

            print("All session data deleted successfully.")
            return deleted_sessions

        except Exception as e:
            print(f"Error deleting all session data: {e}")
            traceback.print_exc()
            return 0




    def get_all_session_data(self) -> Dict[str, Any]:
        """
        Retrieve checkpoint data for all sessions.
        Args:
            checkpointer: The LangGraph checkpointer instance
        Returns:
            A dictionary with session_id as keys and filtered message list as values.
        """
        all_data = {}

        try:
            session_ids = self.list_all_sessions()

            for session_id in session_ids:
                session_data = self.get_session_data(session_id)
                if session_data.get('exists'):
                    all_data[session_id] = session_data.get('messages', [])

            print(f"Retrieved data for {len(all_data)} sessions.")
            return all_data

        except Exception as e:
            print(f"Error retrieving all session data: {e}")
            traceback.print_exc()
            return all_data
