import logging
import os
from typing import Annotated
from langchain_core.tools import tool
from app.utills.tool_output_collector import add_tool_output
from langchain_experimental.utilities import PythonREPL

# Force matplotlib to use non-GUI backend BEFORE any matplotlib import
os.environ['MPLBACKEND'] = 'Agg'

# Initialize REPL and logger
repl = PythonREPL()
logger = logging.getLogger(__name__)

tool_outputs= {}

# Set matplotlib backend in REPL's global namespace
repl.globals['__MATPLOTLIB_BACKEND__'] = 'Agg'

# Pre-configure matplotlib in the REPL environment
MATPLOTLIB_CONFIG = """
import os
os.environ['MPLBACKEND'] = 'Agg'
import matplotlib
matplotlib.use('Agg', force=True)
"""

try:
    repl.run(MATPLOTLIB_CONFIG)
    logger.info("Matplotlib configured for non-GUI backend in REPL")
except:
    pass


@tool
def python_repl_tool(
    code: Annotated[
        str, "The python code to execute to do further analysis or calculation."
    ],
):
    """Use this to execute python code and do data analysis or calculation. 
    
    IMPORTANT: This tool is for COMPUTATION ONLY. NO plotting or visualization.
    - If matplotlib/seaborn/plotly is needed, this tool will FAIL
    - Only use for calculations, data processing, and printing results
    - For charts, use the separate visualization_tool
    
    If you want to see the output of a value, print it out with `print(...)`."""
    
    logger.info(">>>>>>>>>>> Executing Python code")
    
    # Additional safety check
    forbidden_imports = ['matplotlib.pyplot', 'seaborn', 'plotly', '.show()']
    if any(forbidden in code for forbidden in forbidden_imports):
        error_msg = "ERROR: Plotting libraries detected! Use visualization_tool for charts, not python_repl_tool."
        logger.error(error_msg)
        return error_msg
    
    try:
        result = repl.run(code)
        logger.info("Code execution successful")
    except BaseException as e:
        error_msg = f"Failed to execute. Error: {repr(e)}"
        logger.error(error_msg)
        return error_msg
    
    result_str = f"Successfully executed:\n```python\n{code}\n```\nStdout: {result}"
    tool_outputs={'tool_name':"python_repl_tool" ,
                'input_arguments': {'code': code},
                'tool_output': result_str
                }
    try:
        add_tool_output(tool_outputs)
    except Exception:
        pass
    return result_str
