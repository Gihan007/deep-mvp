"""
Visualization Tool - Chart and graph generation
"""

from langchain.tools import tool
import subprocess
import sys
import tempfile
import uuid
import os
from pathlib import Path
import logging
from app.utills.tool_output_collector import add_tool_output


logger = logging.getLogger(__name__)

tool_outputs= {}


def set_dependencies(**kwargs):
    # No dependencies required for this tool currently
    pass


@tool
def visualization_tool(code: str, description: str) -> dict:
    """
    Generate charts and visualizations from provided Python code and return the image path.

    The code must define:
        def generate_and_save_graph(save_dir, filename): ...

    Args:
        code (str): Python code containing a generate_and_save_graph function.
        description (str): brief description of what is going to be visualized

    Returns:
        dict: {
            "image_path": str or None,
            "status": bool,
            "description": str or None
            "error": str or None
        }
    """
    logger.info(">>>>>>>>>>> Executing visualization_tool")
    #logger.info(f"Code length={len(code) if code else 0}")
    try:
        #print("\n>>>>>>>>>>> visualization_tool calling ...\n")
        #print("Generated_code:\n", code, "\n")

        if not code:
            logger.error("No code provided.")
            return {"image_path": None, "description": None , "status": False, "error": "No code provided."}

        # Clean markdown formatting
        cleaned_code = code.strip()
        if "```python" in cleaned_code:
            cleaned_code = cleaned_code.split("```python")[1].split("```")[0].strip()
        elif "```" in cleaned_code:
            cleaned_code = cleaned_code.split("```")[1].split("```")[0].strip()

        # Remove standalone calls
        lines = cleaned_code.split('\n')
        filtered_lines = [line for line in lines if line.strip() != 'generate_and_save_graph()']
        cleaned_code = '\n'.join(filtered_lines)

        if 'def generate_and_save_graph' not in cleaned_code:
            logger.error("Missing function 'generate_and_save_graph'")
            return {"image_path": None, "description": None, "status": False, "error": "Missing function 'generate_and_save_graph'."}

        # ✅ Create a temporary folder for charts
        charts_dir = Path.cwd() / "temp_charts"
        charts_dir.mkdir(parents=True, exist_ok=True)

        chart_filename = f"chart_{uuid.uuid4().hex[:8]}.png"
        temp_script = Path(tempfile.mktemp(suffix=".py"))

        # Write script to temp file
        with open(temp_script, "w") as f:
            f.write("import matplotlib\n")
            f.write("matplotlib.use('Agg')\n")
            f.write("import matplotlib.pyplot as plt\n")
            f.write("import os\n\n")
            f.write(cleaned_code)
            f.write("\n\n")
            f.write("try:\n")
            f.write(f"    result_path = generate_and_save_graph(save_dir=r'{charts_dir}', filename='{chart_filename}')\n")
            f.write("    if os.path.exists(result_path):\n")
            f.write("        print(f'SUCCESS: {result_path}')\n")
            f.write("    else:\n")
            f.write("        print(f'ERROR: File not created at {result_path}')\n")
            f.write("except Exception as e:\n")
            f.write("    import traceback\n")
            f.write("    print(f'ERROR: {str(e)}')\n")
            f.write("    traceback.print_exc()\n")

        # Execute script
        result = subprocess.run(
            [sys.executable, str(temp_script)],
            capture_output=True,
            text=True,
            timeout=30
        )

        os.unlink(temp_script)

        # Handle subprocess errors
        if result.returncode != 0:
            logger.error(f"Code Execution failed: {result.stderr.strip()}")
            return {
                "image_path": None,
                "description": None,
                "status": False,
                "error": f"Execution failed: {result.stderr.strip()}"
            }

        # Parse script output
        for line in result.stdout.strip().split("\n"):
            if line.startswith("SUCCESS:"):
                saved_path = line.replace("SUCCESS:", "").strip()
                logger.info("Visualization generated successfully")
                tool_outputs={'tool_name':"visualization_tool" ,
                            'input_arguments': {'code': code, 'description': description},
                            'tool_output': str(Path(saved_path).absolute())
                            }
                try:
                    add_tool_output(tool_outputs)
                except Exception:
                    pass
                return {"image_path": str(Path(saved_path).absolute()),"description": description, "status": True, "error": None}
            elif line.startswith("ERROR:"):
                error_msg = line.replace("ERROR:", "").strip()
                logger.error(error_msg)
                return {"image_path": None, "description": None, "status": False, "error": error_msg}

        # Fallback: if chart exists but not printed
        expected_path = charts_dir / chart_filename
        if expected_path.exists():
            logger.info("Visualization generated successfully (fallback detection)")
            tool_outputs={'tool_name':"visualization_tool" ,
                        'input_arguments': {'code': code, 'description': description},
                        'tool_output': str(expected_path.absolute())
                        }
            try:
                add_tool_output(tool_outputs)
            except Exception:
                pass
            return {"image_path": str(expected_path.absolute()), "description": description, "status": True, "error": None}
        else:
            logger.error(f"Chart not generated. Output: {result.stdout.strip()}")
            return {
                "image_path": None,
                "status": False,
                "description": None,
                "error": f"Chart not generated. Output: {result.stdout.strip()}"
            }

    except subprocess.TimeoutExpired:
        error_msg = "Execution timed out (30s)."
        logger.error(error_msg)
        return {"image_path": None, "description": None,"status": False, "error": error_msg}
    except Exception as e:
        error_msg = str(e)
        logger.error(error_msg)
        return {"image_path": None, "description": None,"status": False, "error": error_msg}
