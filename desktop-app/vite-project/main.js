import { app, BrowserWindow, Menu } from "electron";
import path from "path";
import { fileURLToPath } from "url";

// ESM equivalents
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

app.setName("AURA");

let mainWindow = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    show: false, // prevents white/black flash
    icon: path.join(__dirname, "public/aura3.png"),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
    },
  });

  // 1️⃣ Load local loading screen immediately
  mainWindow.loadFile(path.join(__dirname, "loading.html"));

  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
  });

  // 2️⃣ Attempt to load localhost app in background
  waitForDevServer(mainWindow);
}

function waitForDevServer(win) {
  const loadApp = async () => {
    try {
      await win.loadURL("http://localhost:5173");
    } catch {
      // Retry until dev server is available
      setTimeout(loadApp, 300);
    }
  };

  loadApp();
}

app.whenReady().then(() => {
  Menu.setApplicationMenu(null);
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
