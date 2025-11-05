"""
Command Line Interface Module
Interactive CLI for Execution Agent

Author: Accessibility AI Team
Version: 1.0.0
"""

import json
import sys
from typing import Dict, Any

from backend.agents.execution_agent.core.exec_agent_config import ExecutionContext
from backend.agents.execution_agent.core.exec_agent_models import ExecutionTask
from backend.agents.execution_agent.core.exec_agent_main import ExecutionAgent


class ExecutionAgentCLI:
    """Command Line Interface for Execution Agent"""
    
    def __init__(self):
        self.agent = ExecutionAgent()
        self.running = True
    
    def print_header(self):
        """Print welcome header"""
        print("\n" + "="*60)
        print("EXECUTION AGENT - Multi-Modal Automation System")
        print("Egyptian Accessibility AI Team")
        print("="*60)
        print("\nAgent Status:")
        status = self.agent.get_status()
        print(f"Platform: {status['platform']}")
        print(f"Version: {status['version']}")
        print("\nAvailable Dependencies:")
        for dep, available in status['dependencies'].items():
            status_icon = "[OK]" if available else "[MISSING]"
            print(f"  {status_icon} {dep}")
        print("="*60 + "\n")
    
    def print_menu(self):
        """Print main menu"""
        print("\n--- MAIN MENU ---")
        print("1. Local Automation (Windows Desktop)")
        print("2. Web Automation (Browser)")
        print("3. System Commands")
        print("4. View Agent Status")
        print("5. View Audit Log")
        print("0. Exit")
        print("-" * 20)
    
    def get_input(self, prompt: str, default: Any = None) -> str:
        """Get user input with optional default"""
        if default:
            prompt = f"{prompt} [{default}]"
        
        value = input(f"{prompt}: ").strip()
        return value if value else (default or "")
    
    def local_automation_menu(self):
        """Local automation submenu"""
        print("\n--- LOCAL AUTOMATION ---")
        print("1. Open Application")
        print("2. Click Element")
        print("3. Type Text")
        print("4. Send Message (Discord/WhatsApp)")
        print("0. Back to Main Menu")
        
        choice = self.get_input("\nSelect action")
        
        if choice == "1":
            self.open_application()
        elif choice == "2":
            self.click_element()
        elif choice == "3":
            self.type_text()
        elif choice == "4":
            self.send_message()
    
    def open_application(self):
        """Open application workflow"""
        print("\n--- OPEN APPLICATION ---")
        app_name = self.get_input("Application name", "Notepad")
        
        task = ExecutionTask(
            action_type="open_app",
            context=ExecutionContext.LOCAL.value,
            strategy="local",
            params={
                "action_type": "open_app",
                "app_name": app_name
            },
            task_id=f"open_app_{app_name.lower().replace(' ', '_')}"
        )
        
        self.execute_task(task)
    
    def click_element(self):
        """Click element workflow"""
        print("\n--- CLICK ELEMENT ---")
        print("Detection Methods:")
        print("1. UIA (Windows Automation)")
        print("2. OCR (Text Recognition)")
        print("3. Computer Vision (Image Template)")
        
        method = self.get_input("Select method", "2")
        
        element_desc = {}
        
        if method == "1":
            element_desc["window_title"] = self.get_input("Window title")
            element_desc["auto_id"] = self.get_input("Auto ID (optional)")
            element_desc["title"] = self.get_input("Element title (optional)")
        
        elif method == "2":
            element_desc["text"] = self.get_input("Text to find")
        
        elif method == "3":
            element_desc["image_path"] = self.get_input("Template image path")
        
        task = ExecutionTask(
            action_type="click_element",
            context=ExecutionContext.LOCAL.value,
            strategy="local",
            params={
                "action_type": "click_element",
                "element": element_desc
            },
            task_id="click_element"
        )
        
        self.execute_task(task)
    
    def type_text(self):
        """Type text workflow"""
        print("\n--- TYPE TEXT ---")
        text = self.get_input("Text to type")
        
        if not text:
            print("Text is required!")
            return
        
        task = ExecutionTask(
            action_type="type_text",
            context=ExecutionContext.LOCAL.value,
            strategy="local",
            params={
                "action_type": "type_text",
                "text": text
            },
            task_id="type_text"
        )
        
        self.execute_task(task)
    
    def send_message(self):
        """Send message workflow"""
        print("\n--- SEND MESSAGE ---")
        platform = self.get_input("Platform (discord/whatsapp)", "discord")
        server_name = self.get_input("Server/Group name")
        message = self.get_input("Message to send")
        channel_image = self.get_input("Channel image path (optional)")
        
        if not message:
            print("Message is required!")
            return
        
        params = {
            "action_type": "send_message",
            "platform": platform,
            "server_name": server_name,
            "message": message
        }
        
        if channel_image:
            params["channel_image"] = channel_image
        
        task = ExecutionTask(
            action_type="send_message",
            context=ExecutionContext.LOCAL.value,
            strategy="local",
            params=params,
            task_id="send_message"
        )
        
        self.execute_task(task)
    
    def web_automation_menu(self):
        """Web automation submenu"""
        print("\n--- WEB AUTOMATION ---")
        print("1. Login to Website")
        print("2. Download File")
        print("3. Fill Form")
        print("0. Back to Main Menu")
        
        choice = self.get_input("\nSelect action")
        
        if choice == "1":
            self.web_login()
        elif choice == "2":
            self.web_download()
        elif choice == "3":
            self.web_fill_form()
    
    def web_login(self):
        """Web login workflow"""
        print("\n--- WEB LOGIN ---")
        url = self.get_input("Website URL")
        username = self.get_input("Username")
        password = self.get_input("Password", "********")
        
        task = ExecutionTask(
            action_type="web_login",
            context=ExecutionContext.WEB.value,
            strategy="selenium",
            params={
                "action_type": "login",
                "url": url,
                "username": username,
                "password": password
            },
            task_id="web_login"
        )
        
        self.execute_task(task)
    
    def web_download(self):
        """Web download workflow"""
        print("\n--- WEB DOWNLOAD ---")
        url = self.get_input("Website URL")
        file_link_text = self.get_input("Download link text")
        
        task = ExecutionTask(
            action_type="web_download",
            context=ExecutionContext.WEB.value,
            strategy="selenium",
            params={
                "action_type": "download_file",
                "url": url,
                "file_link_text": file_link_text
            },
            task_id="web_download"
        )
        
        self.execute_task(task)
    
    def web_fill_form(self):
        """Web form filling workflow"""
        print("\n--- WEB FILL FORM ---")
        url = self.get_input("Website URL")
        
        print("\nEnter form fields (field_name=value), one per line.")
        print("Press Enter on empty line when done.")
        
        form_data = {}
        while True:
            line = input("Field: ").strip()
            if not line:
                break
            
            if "=" in line:
                field, value = line.split("=", 1)
                form_data[field.strip()] = value.strip()
        
        task = ExecutionTask(
            action_type="web_fill_form",
            context=ExecutionContext.WEB.value,
            strategy="selenium",
            params={
                "action_type": "fill_form",
                "url": url,
                "form_data": form_data
            },
            task_id="web_fill_form"
        )
        
        self.execute_task(task)
    
    def system_command_menu(self):
        """System command submenu"""
        print("\n--- SYSTEM COMMANDS ---")
        print("WARNING: System commands can be dangerous!")
        print("High-risk commands will require confirmation.\n")
        
        command = self.get_input("Enter command")
        
        if not command:
            print("Command is required!")
            return
        
        task = ExecutionTask(
            action_type="system_command",
            context=ExecutionContext.SYSTEM.value,
            strategy="subprocess",
            params={
                "command": command
            },
            task_id="system_cmd"
        )
        
        self.execute_task(task)
    
    def execute_task(self, task: ExecutionTask):
        """Execute task and display result"""
        print("\nExecuting task...")
        print(f"Action: {task.action_type}")
        print(f"Context: {task.context}")
        print("-" * 40)
        
        result = self.agent.execute(task)
        
        print("\n--- EXECUTION RESULT ---")
        print(f"Status: {result.status}")
        print(f"Duration: {result.duration:.2f}s")
        print(f"\nDetails: {result.details}")
        
        if result.logs:
            print("\nLogs:")
            for log in result.logs:
                print(f"  • {log}")
        
        if result.error:
            print(f"\nError: {result.error}")
        
        if result.screenshot_path:
            print(f"\nScreenshot: {result.screenshot_path}")
        
        print("-" * 40)
        
        input("\nPress Enter to continue...")
    
    def view_status(self):
        """View agent status"""
        print("\n--- AGENT STATUS ---")
        status = self.agent.get_status()
        print(json.dumps(status, indent=2))
        input("\nPress Enter to continue...")
    
    def view_audit_log(self):
        """View audit log"""
        print("\n--- AUDIT LOG ---")
        audit_log = self.agent.safety_layer.get_audit_log()
        
        if not audit_log:
            print("No audit entries yet.")
        else:
            for i, entry in enumerate(audit_log[-10:], 1):  # Last 10 entries
                print(f"\n{i}. {entry['timestamp']}")
                print(f"   Action: {entry['action']}")
                print(f"   Status: {entry['status']}")
        
        input("\nPress Enter to continue...")
    
    def run(self):
        """Main CLI loop"""
        self.print_header()
        
        while self.running:
            try:
                self.print_menu()
                choice = self.get_input("\nSelect option")
                
                if choice == "1":
                    self.local_automation_menu()
                elif choice == "2":
                    self.web_automation_menu()
                elif choice == "3":
                    self.system_command_menu()
                elif choice == "4":
                    self.view_status()
                elif choice == "5":
                    self.view_audit_log()
                elif choice == "0":
                    print("\nGoodbye!")
                    self.running = False
                else:
                    print("\nInvalid choice!")
            
            except KeyboardInterrupt:
                print("\n\nInterrupted by user. Goodbye!")
                self.running = False
            
            except Exception as e:
                print(f"\nError: {e}")
                import traceback
                traceback.print_exc()


def main():
    """Main entry point"""
    cli = ExecutionAgentCLI()
    cli.run()


if __name__ == "__main__":
    main()
