# Execution Agent Demo - Complete Testing Guide

This guide will walk you through setting up and testing the Execution Agent from scratch.

---

## Prerequisites

Before starting, ensure you have:

* **Python 3.8+** installed
* **Windows 10/11** (the agent is optimized for Windows)
* **Internet connection** (for installing dependencies and web scraping)
* **Microsoft Edge** browser installed (for web automation)

---

## Step 1: Install Python Dependencies

### 1.1 Navigate to Project Directory

Open PowerShell or Command Prompt and navigate to the project folder:

```bash
cd D:\OneDrive\Desktop\GRAD
```

### 1.2 Install Required Packages

Install all dependencies from the requirements file:

```bash
pip install -r exec_agent_requirements.txt
```

**Expected output:** All packages should install successfully. You'll see something like:

```
Successfully installed pyautogui-0.9.54 selenium-4.x.x ...
```

### 1.3 Verify Installation

Verify key dependencies are installed:

```bash
python -c "import pyautogui; import selenium; print('All dependencies installed!')"
```

---

## Step 2: Install Browser Drivers

The Execution Agent uses Selenium for web automation. You need browser drivers:

### 2.1 Edge WebDriver (Recommended)

Edge WebDriver is usually auto-installed with Edge browser, but you can verify:

1. **Check Edge version:**

   * Open Edge browser
   * Go to `edge://settings/help`
   * Note your Edge version (e.g., 120.x.x.x)

2. **EdgeDriver is automatically managed by Selenium 4+**, so no manual installation is needed.

### 2.2 Chrome WebDriver (Fallback)

If you prefer Chrome:

1. Download ChromeDriver from: [https://chromedriver.chromium.org/](https://chromedriver.chromium.org/)
2. Match the version to your Chrome browser version
3. Add ChromeDriver to your PATH or place it in the project folder

---

## Step 3: Verify Project Structure

Ensure you have these files:

```
GRAD/
├── exec_agent_main.py              
├── exec_agent_strategies.py        
├── exec_agent_models.py            
├── exec_agent_config.py            
├── exec_agent_deps.py              
├── exec_agent_action.py            
├── exec_agent_vision.py            
├── exec_agent_safety.py            
├── exec_agent_ppt_handler.py       
├── exec_agent_logger.py            
├── Coordinator.py                  
├── task.json                       
├── search_save_workflow.json       
├── research_report_workflow.json   
├── workflow.json                   
└── exec_agent_requirements.txt     
```

---

## Step 4: Test Basic Functionality

### 4.1 Test Single Task Execution

Test with a simple task:

```bash
python Coordinator.py task.json
```

**Expected result:** The agent should execute the task and print the result.

### 4.2 Test Search & Save Workflow

Test the search and save workflow:

```bash
python Coordinator.py search_save_workflow.json
```

**What it does:**

1. Searches Bing for "latest AI research 2025"
2. Extracts content from the first result
3. Saves to `Desktop/search_results_TIMESTAMP.txt`

**Expected result:**

* Web content extracted
* File saved to Desktop
* Success summary printed

---

## Step 5: Test Research Report Workflow

### 5.1 Basic Test

```bash
python Coordinator.py research_report_workflow.json
```

### 5.2 With Custom Topic

```bash
python Coordinator.py research_report_workflow.json --topic "Machine Learning in Healthcare"
```

### 5.3 With Custom Topic and Report Name

```bash
python Coordinator.py research_report_workflow.json --topic "Quantum Computing" --report-name "QuantumResearch"
```

**What it does:**

1. Creates organized folder: `Desktop/Research_Reports/ReportName_TIMESTAMP/`
2. Extracts web content
3. Saves raw content as `.txt`
4. Creates structured `.json` summary
5. Opens Notepad with report
6. Verifies all files created

**Expected result:**

* Folder created
* Content extracted
* Files saved
* Notepad opens with summary
* Verification successful

**Check output in:**

```
Desktop/Research_Reports/ReportName_TIMESTAMP/
├── source_1_raw.txt
└── research_summary.json
```

---

## Step 6: Test PowerPoint Workflow

### 6.1 Run PowerPoint Demo

```bash
python Coordinator.py workflow.json
```

**What it does:**

1. Opens Edge browser
2. Searches for topic
3. Creates PowerPoint presentation
4. Adds slides with content
5. Saves presentation

**Note:** Make sure Microsoft PowerPoint is installed.

---

## Troubleshooting

### Issue: "Selenium not available"

**Solution:**

```bash
pip install selenium
```

### Issue: "EdgeDriver not found"

**Solution:**

* Ensure Microsoft Edge is installed
* Update Edge to the latest version
* Selenium 4+ should auto-detect EdgeDriver

### Issue: "ModuleNotFoundError: No module named 'X'"

**Solution:**

```bash
pip install -r exec_agent_requirements.txt
```

### Issue: "PowerPoint not opening"

**Solution:**

* Ensure PowerPoint is installed
* Try typing "PowerPoint" in Start Menu to verify
* Check if PowerPoint needs activation

### Issue: "Web content extraction failing"

**Possible causes:**

1. **Bot detection:** Bing may block automation

   * Solution: Wait a few minutes and try again
   * Edge is less likely to trigger bot detection than Chrome
2. **Network issues:**

   * Solution: Check internet connection
3. **Page structure changed:**

   * Solution: The selectors may need updating if Bing changes their HTML

### Issue: "File permission denied"

**Solution:**

* Try saving to a different location (use `--report-name` to change folder)
* Ensure you have write permissions to Desktop
* Try running PowerShell/CMD as Administrator

---

## Step 7: Check Logs

View execution logs:

```bash
# View latest log
type logs\executionagent_*.log | more

# Or open in notepad
notepad logs\executionagent_20251102.log
```

**Log location:** `logs/executionagent_YYYYMMDD.log`

---

## Step 8: Run Interactive Demo (Optional)

For a more interactive experience:

```bash
python exec_agent_demo.py
```

This will:

* Prompt you for a research topic
* Show workflow plan
* Ask for confirmation before execution
* Allow step-by-step execution

---

## Verification Checklist

After setup, verify:

* [ ] All Python packages installed (`pip list` shows required packages)
* [ ] Edge browser is installed and up-to-date
* [ ] Can run `python Coordinator.py task.json` successfully
* [ ] Can run `python Coordinator.py search_save_workflow.json` successfully
* [ ] Files are being created on Desktop
* [ ] Logs are being generated in `logs/` folder

---

## Available Workflows

### 1. `task.json`

**Purpose:** Single task execution
**Usage:** `python Coordinator.py task.json`

### 2. `search_save_workflow.json`

**Purpose:** Search web → Save to file
**Usage:** `python Coordinator.py search_save_workflow.json`

### 3. `research_report_workflow.json`

**Purpose:** Complete research automation
**Usage:** `python Coordinator.py research_report_workflow.json --topic "Your Topic"`

### 4. `workflow.json`

**Purpose:** PowerPoint presentation creation
**Usage:** `python Coordinator.py workflow.json`

---

## Quick Start Commands

```bash
# 1. Install dependencies
pip install -r exec_agent_requirements.txt

# 2. Test single task
python Coordinator.py task.json

# 3. Test search & save
python Coordinator.py search_save_workflow.json

# 4. Test research workflow
python Coordinator.py research_report_workflow.json --topic "Your Topic"

# 5. View logs
notepad logs\executionagent_*.log
```

---

## Additional Resources

* **Main README:** `exec_agent_readme.md`
* **Demo Guide:** `demo_guide.md`
* **Quick Reference:** `quick_reference.md`
* **Architecture:** `architecture_diagram.md`

---

## Getting Help

If you encounter issues:

1. Check logs: `logs/executionagent_*.log`
2. Verify dependencies: `python exec_agent_deps.py`
3. Test single task first: `python Coordinator.py task.json`
4. Check error messages: They usually indicate what's missing

---

## Success Indicators

You'll know everything is working when:

* Tasks execute without errors
* Files are created in expected locations
* Web content is extracted successfully
* Applications open and respond to automation
* Logs show "SUCCESS" status
* No exception errors in console

---

**Happy Testing!**
