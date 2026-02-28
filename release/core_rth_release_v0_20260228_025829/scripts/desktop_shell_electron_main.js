const { app, BrowserWindow, shell, Menu } = require("electron");
const path = require("path");

const DEFAULT_URL = process.env.CORE_RTH_DESKTOP_URL || "http://127.0.0.1:18030/ui/";

function createWindow() {
  const win = new BrowserWindow({
    width: 1480,
    height: 980,
    minWidth: 1080,
    minHeight: 720,
    autoHideMenuBar: false,
    title: "Core Rth",
    backgroundColor: "#07142a",
    webPreferences: {
      preload: path.join(__dirname, "desktop_shell_electron_preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  win.webContents.on("did-fail-load", (_e, code, desc, validatedURL) => {
    const html = `
      <html><body style="margin:0;background:#07142a;color:#e8f2ff;font-family:Segoe UI,Arial,sans-serif">
      <div style="max-width:760px;margin:48px auto;padding:20px;border:1px solid #213a66;border-radius:14px;background:#0d1c38">
        <h1 style="margin-top:0">Core Rth Desktop Shell</h1>
        <p>Impossibile caricare l'interfaccia su <code>${String(validatedURL || DEFAULT_URL)}</code>.</p>
        <p>Verifica che l'API sia attiva:</p>
        <pre style="background:#091126;padding:12px;border-radius:10px;overflow:auto">python scripts\\rth.py api start --port 18030</pre>
        <p>Errore: <code>${code}</code> - ${String(desc || "load failed")}</p>
      </div></body></html>`;
    win.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
  });

  win.loadURL(DEFAULT_URL);

  const template = [
    {
      label: "Core Rth",
      submenu: [
        { role: "reload", label: "Ricarica" },
        { role: "toggleDevTools", label: "DevTools" },
        { type: "separator" },
        {
          label: "Apri API URL",
          click: () => shell.openExternal(DEFAULT_URL),
        },
        { type: "separator" },
        { role: "quit", label: "Esci" },
      ],
    },
    {
      label: "View",
      submenu: [{ role: "reload" }, { role: "forcereload" }, { role: "togglefullscreen" }, { role: "resetzoom" }, { role: "zoomin" }, { role: "zoomout" }],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
