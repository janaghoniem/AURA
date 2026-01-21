# # %%
# %pip install sentence-transformers chromadb tqdm
# %pip install anthropic  dataclasses


# # %%
# %pip install openai torch pandas numpy

# # %%
# %pip install google-generativeai


# # %%
# %pip install groq


# %%
# ============================================================================
# COMPLETE RAG PIPELINE - PART 2: LLM INTEGRATION & CODE GENERATION
# ============================================================================
# This notebook integrates the vector database with LLMs for code generation

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import chromadb
from sentence_transformers import SentenceTransformer
import openai  # Can also use: anthropic, huggingface, ollama
from anthropic import Anthropic
import torch
from dataclasses import dataclass
from datetime import datetime


# %%

# ============================================================================
# CELL 1: Configuration
# ============================================================================

@dataclass
class RAGConfig:
    """Configuration for RAG system"""
    library_name: str = "pywinauto"
    
    # Paths
    vectordb_dir: Path = None
    models_dir: Path = None
    
    # Retrieval settings
    top_k: int = 5  # Number of similar chunks to retrieve
    max_retrieval: int = 15  # ← ADD THIS: Total contexts to retrieve (for 3 retries)

    similarity_threshold: float = 0.3  # Minimum similarity score
    
    # LLM settings
    llm_provider: str = "groq"  # Options: "anthropic", "openai", "ollama", "huggingface"
    llm_model: str = "moonshotai/kimi-k2-instruct-0905"  # or "gpt-4", "gpt-3.5-turbo"
    temperature: float = 0.4  # Lower = more deterministic
    max_tokens: int = 1024
    
    # Code generation settings
    include_context: bool = True
    include_examples: bool = True
    max_context_length: int = 3000  # characters
    
    def __post_init__(self):
        if self.vectordb_dir is None:
            self.vectordb_dir = Path(f"vectordb/{self.library_name}")
        if self.models_dir is None:
            self.models_dir = Path(f"models/{self.library_name}")

config = RAGConfig()
print(f"RAG Configuration for: {config.library_name}")
print(f"LLM Provider: {config.llm_provider}")
print(f"Model: {config.llm_model}")



# %%

# ============================================================================
# CELL 2: Vector Database Interface
# ============================================================================

class VectorDBInterface:
    """Interface to interact with the vector database"""
    
    def __init__(self, config: RAGConfig):
        self.config = config
        self.client = None
        self.collection = None
        self.embedding_model = None
        
    def initialize(self):
        """Initialize connection to vector database"""
        print("Connecting to vector database...")
        
        # Load ChromaDB
        self.client = chromadb.PersistentClient(
            path=str(self.config.vectordb_dir)
        )
        
        # Get collection
        self.collection = self.client.get_collection(
            name=f"{self.config.library_name}_embeddings"
        )
        
        print(f"Connected to collection: {self.collection.name}")
        print(f"Total documents: {self.collection.count()}")
        
        # Load embedding model
        model_path = self.config.models_dir / "embedding_model"
        self.embedding_model = SentenceTransformer(str(model_path))
        print(f"Embedding model loaded")
    
    def search(self, query: str, n_results: int = None) -> Dict:
        """Search for relevant documents"""
        if n_results is None:
            n_results = self.config.top_k
        
        # Generate query embedding
        query_embedding = self.embedding_model.encode([query])[0]
        
        # Search in vector database
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=n_results
        )
        
        return results
    
    def get_relevant_context(self, query: str,max_results: int = None) -> List[Dict]:
        """Get relevant context for a query"""
        if max_results is None:
        # Retrieve MORE contexts for retries (3 attempts × top_k)
            max_results = self.config.max_retrieval  # ← CHANGE: Get 15 instead of 5

        results = self.search(query, n_results=max_results)
        
        contexts = []
        for i, (doc, metadata, distance) in enumerate(zip(
            results['documents'][0],
            results['metadatas'][0],
            results['distances'][0]
        )):
            # Filter by similarity threshold
            similarity = 1 - distance
            if similarity >= self.config.similarity_threshold:
                contexts.append({
                    'rank': i + 1,
                    'content': doc,
                    'metadata': metadata,
                    'similarity': similarity,
                    'distance': distance
                })
        
        return contexts



# %%

# ============================================================================
# CELL 3: LLM Interface (Multi-Provider)
# ============================================================================

class LLMInterface:
    """Interface to interact with different LLM providers"""
    
    def __init__(self, config: RAGConfig):
        self.config = config
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize LLM client based on provider"""
        if self.config.llm_provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                print("⚠️  Warning: ANTHROPIC_API_KEY not found in environment")
            self.client = Anthropic(api_key=api_key) if api_key else None
            
        elif self.config.llm_provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                print("⚠️  Warning: OPENAI_API_KEY not found in environment")
            openai.api_key = api_key
            self.client = "openai"  # Use openai module directly
            
        elif self.config.llm_provider == "ollama":
            # For local Ollama instance
            self.client = "ollama"
            print("Using local Ollama instance")
            
        elif self.config.llm_provider == "gemini":
            self.client = "gemini"
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                 print("⚠️  Warning: GOOGLE_API_KEY not found in environment")
                 self.client = None
            else:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                self.client = genai
        elif self.config.llm_provider == "groq":
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                 print("⚠️  Warning: GROQ_API_KEY not found in environment")
                 self.client = None
            else:
                from groq import Groq
                self.client = Groq(api_key=api_key)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.config.llm_provider}")
    
    def generate(self, prompt: str, system_prompt: str = None) -> str:
        """Generate response from LLM"""
        
        if self.config.llm_provider == "anthropic":
            return self._generate_anthropic(prompt, system_prompt)
        elif self.config.llm_provider == "openai":
            return self._generate_openai(prompt, system_prompt)
        elif self.config.llm_provider == "ollama":
            return self._generate_ollama(prompt, system_prompt)
        elif self.config.llm_provider == "gemini":
            return self._generate_gemini(prompt, system_prompt)
        elif self.config.llm_provider == "groq":
            return self._generate_groq(prompt, system_prompt)

    
    def _generate_anthropic(self, prompt: str, system_prompt: str = None) -> str:
        """Generate using Anthropic Claude"""
        if not self.client:
            return "Error: Anthropic client not initialized. Please set ANTHROPIC_API_KEY."
        
        messages = [{"role": "user", "content": prompt}]
        
        response = self.client.messages.create(
            model=self.config.llm_model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            system=system_prompt if system_prompt else "",
            messages=messages
        )
        
        return response.content[0].text
    
    def _generate_openai(self, prompt: str, system_prompt: str = None) -> str:
        """Generate using OpenAI GPT"""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        response = openai.ChatCompletion.create(
            model=self.config.llm_model,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens
        )
        
        return response.choices[0].message.content
    
    def _generate_ollama(self, prompt: str, system_prompt: str = None) -> str:
        """Generate using local Ollama"""
        import requests
        
        url = "http://localhost:11434/api/generate"
        
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        data = {
            "model": self.config.llm_model,  # e.g., "codellama", "llama2"
            "prompt": full_prompt,
            "stream": False
        }
        
        response = requests.post(url, json=data)
        return response.json()['response']
    
    def _generate_gemini(self, prompt: str, system_prompt: str = None) -> str:
        """Generate using Google Gemini 1.5 Flash"""
        if not self.client:
            return "Error: Gemini client not initialized. Please set GOOGLE_API_KEY."
        
        model = self.client.GenerativeModel(self.config.llm_model)
        
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        else:
            full_prompt = prompt
        
        response = model.generate_content(
            full_prompt,
            generation_config={
                "temperature": self.config.temperature,
                "max_output_tokens": self.config.max_tokens,
            }
    )       
        
        return response.text
    
    def _generate_groq(self, prompt: str, system_prompt: str = None) -> str:
        
        if not self.client:
            return "Error: Groq client not initialized. Please set GROQ_API_KEY."

        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.config.llm_model,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

        return response.choices[0].message.content





# %%

# ============================================================================
# CELL 4: RAG System - Core
# ============================================================================

class RAGSystem:
    """Complete RAG system for code generation"""
    
    def __init__(self, config: RAGConfig):
        self.config = config
        self.vectordb = VectorDBInterface(config)
        self.llm = LLMInterface(config)
        self.conversation_history = []
        
    def initialize(self):
        """Initialize RAG system"""
        print("Initializing RAG System...")
        self.vectordb.initialize()
        print("RAG System ready!")
    
    def generate_code(self, user_query: str, cache_key: str = None,  # ← ADD THIS
                    include_explanation: bool = True,
                    conversation_context: List[Dict] = None,
                    start_context_index: int = 0,  # ← ADD THIS
                    num_contexts: int = None) -> Dict:  # ← ADD THIS
        """
        Generate code based on user query using RAG
        
        Args:
            user_query: The user's request/question
            include_explanation: Whether to include explanation
            conversation_context: Previous conversation for context
            start_context_index: Which context to start from (for retries)
            num_contexts: How many contexts to use (default: top_k)
        """
        if num_contexts is None:
            num_contexts = self.config.top_k
        
        print(f"\n{'='*80}")
        print(f"Query: {user_query}")
        print(f"{'='*80}")
        
        # # Step 1: Retrieve relevant context ONCE (if not already done)
        # if not hasattr(self, '_cached_contexts') or self._cached_query != cache_key:
        #     print("\n[1/3] Retrieving relevant context...")
        #     self._cached_contexts = self.vectordb.get_relevant_context(cache_key)
        #     self._cached_query = cache_key
        #     print(f"Found {len(self._cached_contexts)} relevant documents")
        # else:
        #     print(f"\n[1/3] Using cached contexts ({len(self._cached_contexts)} documents)")
        
        # # Step 2: Select subset of contexts based on retry attempt
        # # Step 2: Select subset of contexts based on retry attempt
        # if start_context_index >= len(self._cached_contexts):
        #     # Instead of raising error, use the last available contexts
        #     print(f"⚠️  Requested index {start_context_index} but only have {len(self._cached_contexts)} contexts")
        #     print(f"⚠️  Using last available contexts instead")
            
        #     # Use the last batch of contexts
        #     start_context_index = max(0, len(self._cached_contexts) - num_contexts)
            
        #     # If we've exhausted all contexts, return None to signal retry failure
        #     if start_context_index == 0 and hasattr(self, '_last_context_index'):
        #         if self._last_context_index == 0:
        #             print("❌ All context windows exhausted")
        #             return {
        #                 'code': '',
        #                 'explanation': 'No more contexts available for retry',
        #                 'full_response': '',
        #                 'contexts_used': 0,
        #                 'top_similarity': 0,
        #                 'references': []
        #             }

        # self._last_context_index = start_context_index  # Track last used index

        # end_index = min(start_context_index + num_contexts, len(self._cached_contexts))
        # contexts = self._cached_contexts[start_context_index:end_index]

        # if not contexts:
        #     print("❌ No contexts available in this window")
        #     return {
        #         'code': '',
        #         'explanation': 'No contexts in requested window',
        #         'full_response': '',
        #         'contexts_used': 0,
        #         'top_similarity': 0,
        #         'references': []
        #     }

        
        # print(f"Using contexts {start_context_index+1} to {min(end_index, len(self._cached_contexts))}")
        
        # for i, ctx in enumerate(contexts[:3]):
        #     print(f"  {start_context_index + i + 1}. Similarity: {ctx['similarity']:.2%} - {ctx['content'][:80]}...")
        contexts=" "
        # Step 3: Build prompt with selected contexts
        print("\n[2/3] Building prompt...")
        prompt = self._build_prompt(user_query, contexts, conversation_context)
        
        print("-" * 40)
        print("\n[2/3.5] printing prompt...")
        print(prompt)
        print("-" * 40)

        prompt_sim="""
Open Microsoft Word using the Start Menu on Windows. 
Use pywinauto to ensure the window opens and is ready. 
Validate that the application is visible and ready for interaction. 
Do not assume the exact path of the executable or window title.
        """
        # Step 4: Generate code
        print("\n[3/3] Generating code...")
        response = self.llm.generate(
            prompt=prompt,
            system_prompt=self._get_system_prompt()
        )
        
        # Parse response
        result = self._parse_response(response, contexts)
        
        # Store in conversation history
        self.conversation_history.append({
            'query': user_query,
            'response': result,
            # 'context_indices': (start_context_index, end_index),
            'timestamp': datetime.now().isoformat()
        })
        
        return result
    
    def _build_prompt(self, query: str, contexts: List[Dict], 
                     conversation_context: List[Dict] = None) -> str:
        """Build the prompt for the LLM"""
        
        prompt_parts = []
        
        # # Add conversation context if available
        # if conversation_context:
        #     prompt_parts.append("## Previous Conversation:")
        #     for msg in conversation_context[-3:]:  # Last 3 messages
        #         prompt_parts.append(f"User: {msg.get('query', '')}")
        #         if 'code' in msg.get('response', {}):
        #             prompt_parts.append(f"Assistant: {msg['response']['code'][:200]}...")
        #     prompt_parts.append("")
        
        # # Add retrieved context
        # prompt_parts.append(f"## Relevant {self.config.library_name} Documentation and Examples:")
        # prompt_parts.append("")
        
        # total_length = 0
        # for i, ctx in enumerate(contexts):
        #     content = ctx['content']
            
        #     # Truncate if needed
        #     if total_length + len(content) > self.config.max_context_length:
        #         content = content[:self.config.max_context_length - total_length]
            
        #     prompt_parts.append(f"### Reference {i+1} (Relevance: {ctx['similarity']:.0%}):")
        #     prompt_parts.append(content)
        #     prompt_parts.append("")
            
        #     total_length += len(content)
            
        #     if total_length >= self.config.max_context_length:
        #         break
        
        # Add user query
        # prompt_parts.append("## User Request:")
        # prompt_parts.append(query)
        # prompt_parts.append("")
        
        # # Add instructions
        # prompt_parts.append("## Instructions:")
        # prompt_parts.append(f"Based on the above {self.config.library_name} documentation and examples, generate:")
        # prompt_parts.append("1. Complete, working Python code that addresses the user's request")
        # prompt_parts.append("2. Include necessary imports")
        # prompt_parts.append("3. Add helpful comments")
        # prompt_parts.append("4. Follow best practices and patterns shown in the examples")
        # prompt_parts.append("")
        # prompt_parts.append("IMPORTANT - Success/Failure Indicators:")  # ← ADD THIS
        # prompt_parts.append("- Your code MUST print success indicators when it completes successfully")
        # prompt_parts.append("- Use keywords: EXECUTION_SUCCESS, SUCCESS, COMPLETED, or DONE")
        # prompt_parts.append("- Example: print('SUCCESS: Window opened and visible')")
        # prompt_parts.append("- For errors, print 'FAILED:' or 'ERROR:' with details")
        # prompt_parts.append("- Always use try-except blocks for risky operations")
        # prompt_parts.append("")
        # prompt_parts.append("Format your response as:")
        # prompt_parts.append("```python")
        # prompt_parts.append("# Your code here")
        # prompt_parts.append("```")
        prompt_parts.append("""Generate automation code to perform the following task:

Task Description:""")
        prompt_parts.append(query)
        prompt_parts.append("""


Requirements

Execute the task exactly as described, without adding extra steps.

Prefer the simplest and most reliable execution method.

If the primary method fails, automatically adapt and try alternative approaches.

Do not assume success—ensure the task is actually performed.

The code must be suitable for use within a multi-agent automation system.

Return only the generated code and necessary explanations, with no assumptions beyond the task description.
""")
        
        return "\n".join(prompt_parts)
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for the LLM"""
        return f"""You are an expert Python automation engineer operating inside a multi-agent
RAG + Execution + Validation system.

Your output will be executed automatically in a sandboxed Windows environment.
It may be retried, validated, cached, compared, or re-executed.

Your primary responsibility is to generate automation code that is:
- Correct
- Minimal
- Deterministic
- Robust in real-world Windows environments

Reliability is more important than cleverness.

================================================================================
EXECUTION CONTEXT AWARENESS (MANDATORY)
================================================================================

- This code is part of an automated execution agent, NOT a script runner.
- Your output may be:
  - Executed multiple times
  - Compared against cached actions
  - Automatically validated based on observable behavior
- Assume NO prior execution state.
- Assume NO application or system state unless explicitly provided.
- Treat every request as fully independent and stateless.

================================================================================
CORE GENERATION PRINCIPLES
================================================================================

1. STRICT INTENT ADHERENCE
- Perform ONLY the action explicitly requested by the user.
- Do NOT infer setup, cleanup, follow-up, or helper actions.
- Do NOT assume missing context.
- Do NOT chain steps unless the user explicitly asks for multiple actions.

2. STATELESS & INDEPENDENT EXECUTION
- Never assume:
  - An application is already open
  - A window is focused
  - A previous task succeeded or failed
- Never rely on history, memory, or prior executions.

3. SIMPLE-FIRST EXECUTION STRATEGY
- Always prefer the most:
  - General
  - Stable
  - Widely supported
  - Non-fragile
  approach.
- Avoid:
  - Hardcoded file paths
  - Application binaries
  - Rare or app-specific shortcuts
  - Deep or brittle UI trees unless required

4. ADAPTIVE EXECUTION MINDSET
- Assume no single perfect method always exists.
- Prefer:
  1. Keyboard-driven interaction
  2. UI automation only if keyboard interaction is insufficient
- Choose approaches that resemble how a real user would perform the task.

================================================================================
FORBIDDEN EXECUTION METHODS (HARD RULES)
================================================================================

- Do NOT use:
  - subprocess
  - os.system
  - os.startfile
  - shell commands
  - PowerShell or cmd
  - Process spawning or execution

This agent is an AUTOMATION agent, not a process launcher.

If an action requires opening or starting something:
- Simulate user interaction via input and UI automation
- Do NOT invoke system-level execution APIs

Any code using forbidden methods will fail validation.

================================================================================
AUTOMATION TOOLING GUIDANCE
================================================================================

- Keyboard interaction is preferred whenever reliable.
- GUI automation is acceptable when keyboard-only interaction is insufficient.
- Backend selection:
  - win32 → classic / legacy desktop applications
  - uia   → modern / dynamic Windows applications
- Prefer top_window() over named window access.
- Avoid brittle assumptions:
  - Do NOT rely on exact window titles
  - Prefer regex or partial matches when needed
  - Avoid hardcoded control IDs or process names

================================================================================
SHORTCUT USAGE RULES
================================================================================

- Do NOT invent or guess shortcuts.
- Only use:
  - Universally standard shortcuts (e.g., Ctrl+C, Ctrl+V, Ctrl+S, Ctrl+N)
  - Shortcuts explicitly provided by the user
- If unsure, choose a more general interaction method.

================================================================================
EXECUTION & VALIDATION RULES
================================================================================

- Always generate COMPLETE, runnable Python code.
- Include all required imports.
- Wrap risky operations in try-except blocks.
- Print execution state exactly once:
  - EXECUTION_SUCCESS → only when the PRIMARY task completes
  - FAILED: <error>   → when the PRIMARY task fails
- Do NOT report failure due to cleanup or secondary steps.
- Print success BEFORE any optional teardown logic.
- Do NOT close or terminate applications unless explicitly requested.

================================================================================
OUTPUT FORMAT (STRICT)
================================================================================

- Output ONLY a single Python code block.
- No explanations.
- No markdown.
- No extra text.

"""

    
    def _parse_response(self, response: str, contexts: List[Dict]) -> Dict:
        """Parse LLM response into structured format"""
        
        # Extract code block
        code = ""
        explanation = ""
        
        if "```python" in response:
            parts = response.split("```python")
            if len(parts) > 1:
                code_part = parts[1].split("```")[0].strip()
                code = code_part
                
                # Get explanation (text after code block)
                remaining = parts[1].split("```", 1)
                if len(remaining) > 1:
                    explanation = remaining[1].strip()
        else:
            # No code block found, treat entire response as explanation
            explanation = response
        
        return {
            'code': code,
            'explanation': explanation,
            'full_response': response
            # 'contexts_used': len(contexts),
            # 'top_similarity': contexts[0]['similarity'] if contexts else 0,
            # 'references': [
            #     {
            #         'source': ctx['metadata'].get('source', 'unknown'),
            #         'similarity': ctx['similarity']
            #     }
            #     for ctx in contexts[:3]
            # ]
        }
    
    def chat(self, message: str) -> Dict:
        """
        Interactive chat interface
        """
        return self.generate_code(
            user_query=message,
            conversation_context=self.conversation_history
        )
    
    def save_conversation(self, filename: str = None):
        """Save conversation history"""
        if filename is None:
            filename = f"conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        filepath = Path("conversations") / filename
        filepath.parent.mkdir(exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.conversation_history, f, indent=2, ensure_ascii=False)
        
        print(f"Conversation saved to {filepath}")



# %%

# ============================================================================
# CELL 5: Code Execution and Testing (Optional)
# ============================================================================

class CodeExecutor:
    """Safely execute generated code for testing"""
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
    
    def execute(self, code: str, test_mode: bool = True) -> Dict:
        """
        Execute code and capture output
        
        Args:
            code: Python code to execute
            test_mode: If True, runs in restricted environment
            
        Returns:
            Dictionary with execution results
        """
        import sys
        from io import StringIO
        import traceback
        
        # Capture output
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        redirected_output = StringIO()
        redirected_error = StringIO()
        
        sys.stdout = redirected_output
        sys.stderr = redirected_error
        
        result = {
            'success': False,
            'output': '',
            'error': '',
            'execution_time': 0
        }
        
        try:
            import time
            start_time = time.time()
            
            # Create restricted globals
            restricted_globals = {
                '__builtins__': __builtins__,
                'print': print,
            }
            
            # Execute code
            exec(code, restricted_globals)
            
            result['success'] = True
            result['execution_time'] = time.time() - start_time
            result['output'] = redirected_output.getvalue()
            
        except Exception as e:
            result['error'] = traceback.format_exc()
            result['output'] = redirected_output.getvalue()
        
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
        
        return result



# %%

# ============================================================================
# CELL 6: Example Usage and Testing
# ============================================================================

def demo_rag_system():
    """Demonstrate the RAG system"""
    
    print("=" * 80)
    print("RAG SYSTEM DEMO")
    print("=" * 80)
    
    # Initialize system
    config = RAGConfig(
        library_name="pywinauto",
        llm_provider="groq",  # Change to "openai" or "ollama" as needed
        top_k=5,
        temperature=0.2
    )
    
    rag = RAGSystem(config)
    rag.initialize()
    
    # Example queries
    test_queries = [
        "How do I click a button in a window using pywinauto?",
        "Show me how to connect to a running application",
        "How do I type text into a text field?",
        "Create code to automate a login dialog with username and password fields"
    ]
    
    for query in test_queries:
        print("\n" + "="*80)
        result = rag.generate_code(query)
        
        print("\n📝 Generated Code:")
        print("-" * 80)
        print(result['code'])
        
        print("\n💡 Explanation:")
        print("-" * 80)
        print(result['explanation'])
        
        print("\n📊 Metadata:")
        print(f"  - Contexts used: {result['contexts_used']}")
        print(f"  - Top similarity: {result['top_similarity']:.2%}")
        print(f"  - References: {result['references']}")
        
        # Optional: Test execution
        # executor = CodeExecutor()
        # exec_result = executor.execute(result['code'])
        # print(f"\n✅ Execution: {'Success' if exec_result['success'] else 'Failed'}")
        
        input("\nPress Enter to continue to next query...")
    
    # Save conversation
    rag.save_conversation()
    
    return rag



# %%

# ============================================================================
# CELL 7: Interactive Chat Interface
# ============================================================================

def interactive_chat():
    """Run interactive chat session"""
    
    print("=" * 80)
    print("🤖 RAG-POWERED CODE ASSISTANT")
    print("=" * 80)
    print("\nInitializing system...")
    
    config = RAGConfig(
        library_name="pywinauto",
        llm_provider="groq",  # Change as needed
        temperature=0.2
    )
    
    rag = RAGSystem(config)
    rag.initialize()
    
    print(f"\n✅ System ready! Ask me anything about {config.library_name}")
    print("Commands: 'quit' to exit, 'save' to save conversation, 'clear' to clear history\n")
    
    while True:
        try:
            user_input = input("\n👤 You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == 'quit':
                print("\n👋 Goodbye!")
                break
            
            if user_input.lower() == 'save':
                rag.save_conversation()
                continue
            
            if user_input.lower() == 'clear':
                rag.conversation_history = []
                print("✅ Conversation history cleared")
                continue
            
            # Generate response
            result = rag.chat(user_input)
            
            print("\n🤖 Assistant:\n")
            
            if result['code']:
                print("```python")
                print(result['code'])
                print("```\n")
            
            if result['explanation']:
                print(result['explanation'])
            
            print(f"\n📊 (Used {result['contexts_used']} references, "
                  f"top similarity: {result['top_similarity']:.1%})")
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()



# %%


# %%

# ============================================================================
# CELL 8: Run Demo or Interactive Mode
# ============================================================================

if __name__ == "__main__":
    import sys
    
    # Set your API key here or in environment
    # os.environ["OPENAI_API_KEY"] = "your-api-key-here"
    
    
    print("\nChoose mode:")
    print("1. Demo mode (run example queries)")
    print("2. Interactive chat")
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    if choice == "1":
        rag_system = demo_rag_system()
    elif choice == "2":
        interactive_chat()
    else:
        print("Invalid choice. Running demo mode...")
        rag_system = demo_rag_system()



# %%
