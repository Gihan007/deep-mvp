# File: tools/tool_initializer.py
"""
Tool initialization and dependency management
"""


class ToolInitializer:
    """Handles initialization of all tool dependencies"""
    
    def __init__(self, graphdb_vector_store, chromadb_vector_store, llm, config):
        self.graphdb_vector_store = graphdb_vector_store
        self.chromadb_vector_store = chromadb_vector_store
        self.llm = llm
        self.config = config
        self.dependencies = {}
        
    def initialize_all(self):
        from . import ALL_TOOLS
        return ALL_TOOLS


    def _configure_tools(self):
        """Configure all tool modules with dependencies"""
        import importlib
        # List of tool module names
        tool_modules = [
            'graph_db_vector_search_tool', 
        ]
        
        parent_package = '.'.join(__name__.split('.')[:-1])
        for module_name in tool_modules:
            try:
                full_module_name = f'{parent_package}.{module_name}'
                module = importlib.import_module(full_module_name)
                if hasattr(module, 'set_dependencies'):
                    module.set_dependencies(graphdb_vector_store=self.graphdb_vector_store,
                                            chromadb_vector_store=self.chromadb_vector_store,
                                            llm=self.llm,
                                            **self.dependencies)
                else:
                    print(f"Warning: Module {module_name} does not have set_dependencies function")
                    
            except ImportError as e:
                print(f"Warning: Could not import module {module_name}: {e}")