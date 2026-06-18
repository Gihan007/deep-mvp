"""
Approval checker node - detects if user has confirmed a database update
"""
from langchain_core.messages import AIMessage, HumanMessage
import logging

logger = logging.getLogger(__name__)

def check_user_approval(state):
    """
    Check if the last exchange was: AI asked for confirmation → User said yes
    Set user_approved_update flag accordingly
    """
    messages = state.get('messages', [])
    
    # Look for pattern: Last AI message asked for approval + Last human message confirmed
    last_ai = None
    last_human = None
    
    # Get last 2 messages (should be AI question + Human response)
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and last_ai is None:
            last_ai = msg
        elif isinstance(msg, HumanMessage) and last_human is None:
            last_human = msg
        if last_ai and last_human:
            break
    
    # Check if this is a confirmation scenario
    if last_ai and last_human:
        ai_content = last_ai.content.lower()
        human_content = last_human.content.lower().strip()
        
        # Check if AI asked for confirmation
        asked_for_approval = any(phrase in ai_content for phrase in [
            'do you want me to',
            'proceed with this change',
            'should i proceed',
            'please confirm',
            'would you like to proceed'
        ])
        
        # Check if human confirmed YES
        user_said_yes = human_content in ['yes', 'ok', 'okay', 'proceed', 'confirm', 'sure', 'go ahead', 'y']
        
        # Check if human rejected NO
        user_said_no = any(phrase in human_content for phrase in ['no', 'nope', 'cancel', 'stop', 'don\'t', 'do not', 'no need', 'never mind', 'abort'])
        
        # CRITICAL: Check if human is making a NEW request (not just answering yes/no)
        # If the human message contains words like "change", "update", "set", "delete", it's a NEW request
        is_new_request = any(keyword in human_content for keyword in ['change', 'update', 'set', 'modify', 'delete', 'create', 'add', 'remove'])
        
        # CHECK NEW REQUEST FIRST - before checking approval/rejection
        if is_new_request:
            logger.info(f"🔄 NEW REQUEST DETECTED: User is making a new request: '{human_content}'")
            state['user_approved_update'] = False
            state['user_rejected_update'] = False
            return state
        
        # Now check for approval (only if NOT a new request)
        if asked_for_approval and user_said_yes:
            logger.info(f"✅ USER APPROVAL DETECTED: Agent asked for confirmation and user said '{human_content}'")
            state['user_approved_update'] = True
            state['user_rejected_update'] = False
            
            # Inject a system message to guide the supervisor
            approval_guidance = AIMessage(content="[SYSTEM] User approved the update. Routing to update agent to execute the change.",name="system")
            state['messages'].append(approval_guidance)
            logger.info("   💬 Injected approval guidance for supervisor")
            return state
        
        # Check for rejection (only if NOT a new request)
        if asked_for_approval and user_said_no:
            logger.info(f"🚫 USER REJECTION DETECTED: Agent asked for confirmation and user said '{human_content}'")
            state['user_approved_update'] = False
            state['user_rejected_update'] = True
            
            # Inject a direct AI response acknowledging the rejection
            rejection_response = AIMessage(
                content="Understood, I won't make that change. The data will remain as is. Is there anything else I can help you with?",
                name="graphdb_update_graph_agent"
            )
            state['messages'].append(rejection_response)
            logger.info("   💬 Injected rejection acknowledgment message")
            return state
    
    # No approval or rejection detected
    state['user_approved_update'] = False
    state['user_rejected_update'] = False
    return state




