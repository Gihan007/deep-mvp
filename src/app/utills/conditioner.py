from app.prompts.prompts  import question_classifier_prompt
import os
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage



class QestionClassifier:
    def __init__(self, llm):
        self.llm = llm
        self.question_classifier_prompt = question_classifier_prompt(self.llm)

    def classifier(self, state):
        
        messages = state["messages"]
        last_human_index = None
        for i in reversed(range(len(messages))):
            if isinstance(messages[i], HumanMessage):
                last_human_index = i
                break
        if last_human_index is None:
            raise ValueError("No human message found in state['messages']")
        
        last_human_message = messages[last_human_index]
        chat_history = messages[:last_human_index] + messages[last_human_index + 1:]
        
        # Chat flow classifier
        score = self.question_classifier_prompt.invoke({"chat_history": chat_history, "question": last_human_message})
        grade = score["score"]
        
        if grade == "yes":
            print("---DECISION: GENERAL SMALL TALK - Route to GeneralQA---")
            print(" ")
            print(" ")
            return "yes"
        else:
            print("---DECISION: CONTEXT-AWARE QUESTION - Route to ContextAwareQA---")
            print(" ")
            print(" ")
            return "no"




class ToolConditioner:
    def __init__(self):
        pass
        
    def conditioner(self, state):
        """
        Use in the conditional_edge to route to the ToolNode if the last message
        has tool calls. Otherwise, route to the end.
        """
        try:

            messages = state["messages"]
            last_message = messages[-1]
            if not last_message.tool_calls: 
                return "end"
            else:
                return "tool_node"
            
        except Exception as e:
            print(f"Error in tool conditioner: {str(e)}")
            return "end_node"