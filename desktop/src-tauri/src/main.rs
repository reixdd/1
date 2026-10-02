#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{
    env,
    io::{Read, Write},
    net::{SocketAddr, TcpStream},
    path::PathBuf,
    process::{Command, Stdio},
    time::{Duration, Instant},
};

use tauri::{
    menu::MenuBuilder,
    tray::TrayIconBuilder,
    AppHandle, Manager, WebviewUrl, WebviewWindowBuilder, WindowEvent,
};
use tauri_plugin_autostart::ManagerExt as AutostartManagerExt;
use tauri_plugin_global_shortcut::ShortcutState;
use tauri_plugin_notification::NotificationExt;

const CORE_ADDR: &str = "127.0.0.1:8768";
const CORE_VERSION: &str = "0.3.1";

fn allowed_path(path: &str) -> bool {
    path == "/" || path == "/health" || path.starts_with("/api/")
}

fn core_http_get(path: &str) -> Result<String, String> {
    if !allowed_path(path) {
        return Err("desktop only permits the local JARVIS read-only API surface".into());
    }
    let addr: SocketAddr = CORE_ADDR.parse().map_err(|e| format!("bad core address: {e}"))?;
    let mut stream = TcpStream::connect_timeout(&addr, Duration::from_millis(900))
        .map_err(|e| format!("JARVIS Core is offline: {e}"))?;
    stream
        .set_read_timeout(Some(Duration::from_secs(3)))
        .map_err(|e| e.to_string())?;
    stream
        .set_write_timeout(Some(Duration::from_secs(2)))
        .map_err(|e| e.to_string())?;

    let request = format!(
        "GET {path} HTTP/1.1\r\nHost: 127.0.0.1:8768\r\nAccept: application/json\r\nConnection: close\r\n\r\n"
    );
    stream.write_all(request.as_bytes()).map_err(|e| e.to_string())?;
    let mut bytes = Vec::new();
    stream.read_to_end(&mut bytes).map_err(|e| e.to_string())?;
    let response = String::from_utf8_lossy(&bytes);
    let (head, body) = response
        .split_once("\r\n\r\n")
        .ok_or_else(|| "invalid local core HTTP response".to_string())?;
    let status = head.lines().next().unwrap_or_default();
    if !status.contains(" 200 ") {
        return Err(format!("JARVIS Core returned {status}"));
    }
    Ok(body.to_string())
}

fn core_is_running() -> bool {
    let Ok(addr) = CORE_ADDR.parse::<SocketAddr>() else { return false; };
    TcpStream::connect_timeout(&addr, Duration::from_millis(180)).is_ok()
}

fn install_root() -> Result<PathBuf, String> {
    let home = env::var_os("USERPROFILE").ok_or("USERPROFILE is unavailable")?;
    Ok(PathBuf::from(home).join("JARVIS"))
}

#[cfg(windows)]
fn spawn_core_process() -> Result<(), String> {
    use std::os::windows::process::CommandExt;
    const CREATE_NO_WINDOW: u32 = 0x08000000;

    let root = install_root()?;
    let python = root.join(".venv").join("Scripts").join("python.exe");
    if !python.exists() {
        return Err(format!("clean JARVIS venv not found at {}", python.display()));
    }
    Command::new(&python)
        .arg("-m")
        .arg("jarvis")
        .current_dir(&root)
        .env("JARVIS_HOST", "127.0.0.1")
        .env("JARVIS_PORT", "8768")
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .creation_flags(CREATE_NO_WINDOW)
        .spawn()
        .map_err(|e| format!("failed to start clean JARVIS Core: {e}"))?;
    Ok(())
}

#[cfg(not(windows))]
fn spawn_core_process() -> Result<(), String> {
    Err("Step 4 desktop build is Windows-only".into())
}

fn ensure_core_blocking() -> Result<String, String> {
    if !core_is_running() {
        spawn_core_process()?;
        let started = Instant::now();
        while started.elapsed() < Duration::from_secs(15) {
            if core_is_running() { break; }
            std::thread::sleep(Duration::from_millis(250));
        }
    }
    let root = core_http_get("/")?;
    if !root.contains(&format!("\"version\":\"{CORE_VERSION}\""))
        && !root.contains(&format!("\"version\": \"{CORE_VERSION}\""))
    {
        return Err(format!(
            "port 8768 answered, but it is not the verified JARVIS Core {CORE_VERSION}: {root}"
        ));
    }
    Ok(root)
}

#[tauri::command]
async fn core_get(path: String) -> Result<String, String> {
    tauri::async_runtime::spawn_blocking(move || core_http_get(&path))
        .await
        .map_err(|e| format!("core request task failed: {e}"))?
}

#[tauri::command]
async fn ensure_core_running() -> Result<String, String> {
    tauri::async_runtime::spawn_blocking(ensure_core_blocking)
        .await
        .map_err(|e| format!("core startup task failed: {e}"))?
}

#[tauri::command]
fn core_running() -> bool { core_is_running() }

#[tauri::command]
fn autostart_status(app: AppHandle) -> Result<bool, String> {
    app.autolaunch().is_enabled().map_err(|e| e.to_string())
}

#[tauri::command]
fn set_autostart(app: AppHandle, enabled: bool) -> Result<bool, String> {
    if enabled {
        app.autolaunch().enable().map_err(|e| e.to_string())?;
    } else {
        app.autolaunch().disable().map_err(|e| e.to_string())?;
    }
    app.autolaunch().is_enabled().map_err(|e| e.to_string())
}

#[tauri::command]
fn notify_attention(app: AppHandle, title: String, body: String) -> Result<(), String> {
    app.notification()
        .builder()
        .title(title)
        .body(body)
        .show()
        .map_err(|e| e.to_string())
}

fn show_main(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
    }
}

fn toggle_compact_window(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("compact") {
        if window.is_visible().unwrap_or(false) {
            let _ = window.hide();
        } else {
            let _ = window.show();
            let _ = window.set_focus();
        }
    }
}

#[tauri::command]
fn show_workstation(app: AppHandle) { show_main(&app); }

#[tauri::command]
fn hide_workstation(app: AppHandle) {
    if let Some(window) = app.get_webview_window("main") { let _ = window.hide(); }
}

#[tauri::command]
fn toggle_compact(app: AppHandle) { toggle_compact_window(&app); }

fn main() {
    let shortcut_plugin = tauri_plugin_global_shortcut::Builder::new()
        .with_shortcuts(["ctrl+shift+j"])
        .expect("failed to configure Ctrl+Shift+J")
        .with_handler(|app, _shortcut, event| {
            if event.state == ShortcutState::Pressed {
                toggle_compact_window(app);
            }
        })
        .build();

    tauri::Builder::default()
        // Must be registered first: second launches focus the existing workstation.
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| show_main(app)))
        .plugin(shortcut_plugin)
        .plugin(
            tauri_plugin_autostart::Builder::new()
                .arg("--minimized")
                .app_name("JARVIS Market Intelligence")
                .build(),
        )
        .plugin(tauri_plugin_notification::init())
        .invoke_handler(tauri::generate_handler![
            core_get,
            ensure_core_running,
            core_running,
            autostart_status,
            set_autostart,
            notify_attention,
            show_workstation,
            hide_workstation,
            toggle_compact,
        ])
        .setup(|app| {
            // Compact overlay is separate from the full workstation and starts hidden.
            WebviewWindowBuilder::new(
                app,
                "compact",
                WebviewUrl::App("index.html?mode=compact".into()),
            )
            .title("JARVIS Compact")
            .inner_size(500.0, 650.0)
            .min_inner_size(420.0, 500.0)
            .resizable(true)
            .decorations(false)
            .always_on_top(true)
            .skip_taskbar(true)
            .visible(false)
            .build()?;

            let menu = MenuBuilder::new(app)
                .text("open", "Open Workstation")
                .text("compact", "Toggle Compact  Ctrl+Shift+J")
                .separator()
                .text("core", "Ensure Research Core")
                .separator()
                .text("quit", "Quit Desktop")
                .build()?;

            TrayIconBuilder::new()
                .menu(&menu)
                .tooltip("JARVIS Market Intelligence")
                .icon(app.default_window_icon().expect("default app icon").clone())
                .show_menu_on_left_click(false)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "open" => show_main(app),
                    "compact" => toggle_compact_window(app),
                    "core" => { let _ = ensure_core_blocking(); },
                    "quit" => app.exit(0),
                    _ => {}
                })
                .build(app)?;

            let minimized = env::args().any(|arg| arg == "--minimized");
            if minimized {
                if let Some(main) = app.get_webview_window("main") { let _ = main.hide(); }
            }

            // Core startup is isolated from the UI. A failed core start leaves the tray alive.
            std::thread::spawn(|| { let _ = ensure_core_blocking(); });
            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running JARVIS desktop");
}
