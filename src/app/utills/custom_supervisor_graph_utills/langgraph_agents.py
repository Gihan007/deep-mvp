import sys
import functools
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


class AgentNode():
    def __init__(self, llm, agent_name: str, agent_tools: list, system_message: str):
        self.agent_name = agent_name
        self.agent_tools = agent_tools
        self.system_message = system_message
        self.llm = llm

        # Build the agent per invocation so system_message can be dynamic (e.g., includes real-time CURRENT_TIME)
        self.agent_node = functools.partial(self.agent_executor, name=self.agent_name)

    def agent_executor(self, state, name):
        try:
            # Resolve system message dynamically if a callable is provided; else use the static string
            system_message = self.system_message() if callable(self.system_message) else self.system_message
            agent = self.create_agent(self.llm, self.agent_tools, system_message)

            result = agent.invoke(state['messages'])

            # Normalize to AIMessage unless already an AIMessage or a ToolMessage
            if not isinstance(result, (AIMessage, ToolMessage)):
                result = AIMessage(**result.dict(exclude={"type", "name"}), name=name)

            return {
                "messages":[result],
                "sender": name
            }

        except Exception as ex:
            exception = "AN EXCEPTION OCCURRED IN {filename} AND FUNC {method}() AT {line_no}: {ex}".format(
                    filename="langgraph_agents.py",
                    method="AgentNode",
                    line_no=sys.exc_info()[2].tb_lineno,
                    ex=ex,
                )

            raise exception

    def create_agent(self, llm, agent_tool, system_message: str, output_parser=None):
        try:

            prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        "You are a helpful AI assistant, collaborating with other assistants."
                        " Use the provided tools to progress towards answering the question."
                        " Execute what you can to make progress and then hand back to the supervisor for routing."
                        " Do NOT finalize the conversation yourself."
                        " Only prefix STOP: when asking a clarifying question per the attached policy."
                        " Never prefix STOP in normal answers."
                        " Always use the bound tools to retrieve data rather than answering from prior knowledge."
                        " {tool_message}\n{system_message}",
                    ),
                    MessagesPlaceholder(variable_name="messages"),
                ]
            )
            prompt = prompt.partial(system_message=system_message)

            if agent_tool:
                tools_names = ", ".join([tool.name for tool in agent_tool])
                prompt = prompt.partial(tool_message=f"You have access to the following tools: {tools_names}.\n")                
                agent = prompt | llm.bind_tools(agent_tool)

            else:
                prompt = prompt.partial(tool_message="You have access to the following tools: ")
                agent = prompt | llm

            return agent

        except Exception as ex:
            exception = "AN EXCEPTION OCCURRED IN {filename} AND FUNC {method}() AT {line_no}: {ex}".format(
                    filename="langgraph_agents.py",
                    method="create_agent",
                    line_no=sys.exc_info()[2].tb_lineno,
                    ex=ex,
                )

            raise exception
