#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use tauri::{Manager, PhysicalPosition};
use tauri::menu::MenuBuilder;
use tauri::tray::TrayIconBuilder;
use std::time::Duration;

const CORE_ORIGIN: &str = "http://127.0.0.1:8768";
const ALLOWED_PATHS: &[&str] = &[
  "/health", "/api/operator/radar", "/api/operator/dossier",
  "/api/operator/chart", "/api/operator/gmgn/status",
  "/api/operator/gmgn/trenches", "/api/operator/gmgn/token",
  "/api/attention", "/api/models",
];

fn validated_url(path: &str) -> Result<reqwest::Url, String> {
  if path.len() > 1024 || !path.starts_with('/') || path.starts_with("//") ||
     path.chars().any(|c| c.is_control()) || (path.contains('\\') || path.contains('#')) ||
     path.contains("..") || path.contains('%') {
    return Err("Invalid local research path".into());
  }
  let url = reqwest::Url::parse(&format!("{CORE_ORIGIN}{path}"))
    .map_err(|_| "Invalid local research URL")?;
  if url.scheme() != "http" || url.host_str() != Some("127.0.0.1") ||
     url.port_or_known_default() != Some(8768) || !ALLOWED_PATHS.contains(&url.path()) ||
     !url.username().is_empty() || url.password().is_some() || url.fragment().is_some() {
    return Err("Read-only research endpoint not permitted".into());
  }
  let pairs: Vec<_> = url.query_pairs().collect();
  for (key, _) in &pairs {
    if !["limit", "chain", "contract", "identity_key", "address", "gmgn", "holders"].contains(&key.as_ref()) {
      return Err("Research query parameter not permitted".into());
    }
  }
  Ok(url)
}

#[tauri::command]
async fn core_get(path: String) -> Result<String, String> {
  let url = validated_url(&path)?;
  let client = reqwest::Client::builder()
    .timeout(Duration::from_secs(8))
    .redirect(reqwest::redirect::Policy::none())
    .build().map_err(|e| e.to_string())?;
  let response = client.get(url).send().await.map_err(|e| format!("JARVIS unavailable: {e}"))?;
  if !response.status().is_success() {return Err(format!("JARVIS returned {}",response.status().as_u16()));}
  if response.content_length().unwrap_or(0)>2_000_000 {return Err("Core response too large".into());}
  let bytes=response.bytes().await.map_err(|e|e.to_string())?;
  if bytes.len()>2_000_000{return Err("Core response too large".into());}
  String::from_utf8(bytes.to_vec()).map_err(|_| "Core returned invalid UTF-8".into())
}

#[tauri::command]
fn set_always_on_top(window: tauri::WebviewWindow, enabled: bool) -> Result<(), String> {
 window.set_always_on_top(enabled).map_err(|e|e.to_string())
}

fn main(){
 tauri::Builder::default()
 .invoke_handler(tauri::generate_handler![core_get,set_always_on_top])
 .setup(|app|{
   if let Some(main)=app.get_webview_window("main"){
     if let Ok(Some(monitor))=main.current_monitor(){
       let size=monitor.size();let pos=monitor.position();
       let target_x=pos.x+size.width as i32-420;
       let _=main.set_position(PhysicalPosition::new(target_x,pos.y+40));
     }
   }
   let menu=MenuBuilder::new(app).text("show","Show MIKA").text("quit","Quit MIKA").build()?;
   TrayIconBuilder::new().menu(&menu)
    .tooltip("MIKA · Research only")
    .icon(app.default_window_icon().expect("app icon").clone())
    .on_menu_event(|app,event|match event.id.as_ref(){
      "show"=>{if let Some(window)=app.get_webview_window("main"){let _=window.show();let _=window.set_focus();}},
      "quit"=>app.exit(0),_=>{}
    }).build(app)?;
   Ok(())
 })
 .run(tauri::generate_context!())
 .expect("Unable to start MIKA");
}

#[cfg(test)]
mod tests {
 use super::validated_url;
 #[test] fn allowed_read_only_routes(){ assert!(validated_url("/health").is_ok());assert!(validated_url("/api/operator/dossier?chain=sol&contract=So11111111111111111111111111111111111111112").is_ok());}
 #[test] fn blocks_arbitrary_local_routes(){for p in ["/api/chat", "/api/operator/watch", "http://evil.test/health", "//evil.test/health", "/api/operator/../chat", "/api/%6fh"] {assert!(validated_url(p).is_err(),"accepted: {p}");}}
 #[test] fn blocks_request_injection(){for p in ["/health\r\nHost: evil", "/health#fragment", "/health\\abc", "/health?secret=abc"]{assert!(validated_url(p).is_err(),"accepted: {p}");}}
}
