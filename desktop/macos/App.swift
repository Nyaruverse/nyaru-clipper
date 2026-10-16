import AppKit
import WebKit

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKDownloadDelegate, WKUIDelegate {
    var window: NSWindow!
    var web: WKWebView!
    var helper: Process?
    var timer: Timer?
    var origin: URL?
    var ready: URL!
    var log: FileHandle?
    var attempts = 0
    var checking = false
    var quitting = false
    var exports: [ObjectIdentifier: (temporary: URL, destination: URL, replacing: Bool)] = [:]

    func applicationDidFinishLaunching(_ notification: Notification) {
        let mainMenu = NSMenu()
        let appItem = NSMenuItem()
        mainMenu.addItem(appItem)
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "退出 Nyaru Clipper", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appItem.submenu = appMenu
        let editItem = NSMenuItem(title: "编辑", action: nil, keyEquivalent: "")
        mainMenu.addItem(editItem)
        let editMenu = NSMenu(title: "编辑")
        for (title, selector, key) in [("撤销", "undo:", "z"), ("剪切", "cut:", "x"), ("复制", "copy:", "c"), ("粘贴", "paste:", "v"), ("全选", "selectAll:", "a")] {
            editMenu.addItem(withTitle: title, action: Selector(selector), keyEquivalent: key)
        }
        editItem.submenu = editMenu
        NSApp.mainMenu = mainMenu

        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1260, height: 860), styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "Nyaru Clipper"
        window.minSize = NSSize(width: 760, height: 560)
        web = WKWebView(frame: window.contentView!.bounds)
        web.autoresizingMask = [.width, .height]
        web.navigationDelegate = self
        web.uiDelegate = self
        window.contentView = web
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        web.loadHTMLString("<html lang='zh'><body style='font:18px -apple-system;padding:60px;background:#faf8f4'><h1>Nyaru Clipper</h1><p>正在启动本地工作台…</p><p>首次启动正在准备语音模型，请稍候。</p></body></html>", baseURL: nil)
        do {
            let data = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("Nyaru Clipper", isDirectory: true)
            try FileManager.default.createDirectory(at: data, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
            ready = data.appendingPathComponent("startup-\(UUID().uuidString).json")
            let logURL = data.appendingPathComponent("app.log")
            FileManager.default.createFile(atPath: logURL.path, contents: nil)
            log = try FileHandle(forWritingTo: logURL)
            let process = Process()
            process.executableURL = Bundle.main.resourceURL!.appendingPathComponent("runtime/nyaru-backend/nyaru-backend")
            process.arguments = ["--data", data.path, "--ready", ready.path, "--parent-pid", String(getpid())]
            process.environment = ["PATH": "/usr/bin:/bin", "HOME": NSHomeDirectory(), "LANG": "en_US.UTF-8"]
            process.standardOutput = log
            process.standardError = log
            process.terminationHandler = { [weak self] process in
                DispatchQueue.main.async {
                    guard let self, !self.quitting else { return }
                    self.fail("本地服务已退出（\(process.terminationStatus)）。请查看应用数据目录中的 app.log。")
                }
            }
            helper = process
            try process.run()
            timer = Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { [weak self] _ in
                MainActor.assumeIsolated { self?.checkReady() }
            }
        } catch { fail(error.localizedDescription) }
    }

    func checkReady() {
        attempts += 1
        if attempts > 480 { fail("启动超过两分钟，请查看应用数据目录中的 app.log。"); return }
        guard !checking, let bytes = try? Data(contentsOf: ready),
              let payload = try? JSONSerialization.jsonObject(with: bytes) as? [String: Any],
              let value = payload["url"] as? String, let url = URL(string: value),
              url.host == "127.0.0.1", payload["pid"] as? Int == Int(helper?.processIdentifier ?? 0) else { return }
        checking = true
        URLSession.shared.dataTask(with: url.appendingPathComponent("companion-api/config")) { [weak self] _, response, _ in
            DispatchQueue.main.async {
                guard let self else { return }
                self.checking = false
                guard !self.quitting, (response as? HTTPURLResponse)?.statusCode == 200 else { return }
                self.timer?.invalidate()
                self.origin = url
                self.web.load(URLRequest(url: url))
            }
        }.resume()
    }

    func fail(_ message: String) {
        timer?.invalidate()
        let alert = NSAlert()
        alert.messageText = "无法启动本地工作台"
        alert.informativeText = message
        alert.addButton(withTitle: "退出")
        alert.runModal()
        NSApp.terminate(nil)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        if quitting { return .terminateNow }
        quitting = true
        timer?.invalidate()
        guard let process = helper, process.isRunning else { return .terminateNow }
        let pid = process.processIdentifier
        if kill(-pid, SIGTERM) != 0 { process.terminate() }
        DispatchQueue.global().async {
            Thread.sleep(forTimeInterval: 3)
            kill(-pid, SIGKILL)
            DispatchQueue.main.async { NSApp.reply(toApplicationShouldTerminate: true) }
        }
        return .terminateLater
    }

    func applicationWillTerminate(_ notification: Notification) {
        if let ready { try? FileManager.default.removeItem(at: ready) }
        for target in exports.values { try? FileManager.default.removeItem(at: target.temporary) }
        try? log?.close()
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url, let origin else { decisionHandler(.allow); return }
        if url.scheme == origin.scheme && url.host == origin.host && url.port == origin.port {
            decisionHandler(navigationAction.shouldPerformDownload ? .download : .allow)
        } else {
            if navigationAction.navigationType == .linkActivated, ["https", "http"].contains(url.scheme ?? "") { NSWorkspace.shared.open(url) }
            decisionHandler(.cancel)
        }
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationResponse: WKNavigationResponse, decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        let attachment = (navigationResponse.response as? HTTPURLResponse)?.value(forHTTPHeaderField: "Content-Disposition")?.lowercased().hasPrefix("attachment") == true
        decisionHandler(navigationResponse.canShowMIMEType && !attachment ? .allow : .download)
    }

    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) { download.delegate = self }
    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) { download.delegate = self }

    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        guard let origin, let port = origin.port, frame.securityOrigin.host == origin.host,
              frame.securityOrigin.port == port else { completionHandler(nil); return }
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = parameters.allowsDirectories
        panel.allowsMultipleSelection = parameters.allowsMultipleSelection
        panel.beginSheetModal(for: window) { result in
            completionHandler(result == .OK ? panel.urls : nil)
        }
    }

    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        guard let origin, frame.securityOrigin.host == origin.host, frame.securityOrigin.port == origin.port else { completionHandler(false); return }
        let alert = NSAlert()
        alert.messageText = "确认字幕操作"
        alert.informativeText = message
        alert.addButton(withTitle: "继续")
        alert.addButton(withTitle: "取消")
        alert.beginSheetModal(for: window) { response in completionHandler(response == .alertFirstButtonReturn) }
    }

    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse, suggestedFilename: String, completionHandler: @escaping (URL?) -> Void) {
        let panel = NSSavePanel()
        panel.nameFieldStringValue = (suggestedFilename as NSString).lastPathComponent
        panel.canCreateDirectories = true
        panel.beginSheetModal(for: window) { result in
            guard result == .OK, let destination = panel.url else { completionHandler(nil); return }
            let temporary = destination.deletingLastPathComponent().appendingPathComponent(".nyaru-\(UUID().uuidString).download")
            self.exports[ObjectIdentifier(download)] = (temporary, destination, FileManager.default.fileExists(atPath: destination.path))
            completionHandler(temporary)
        }
    }

    func downloadDidFinish(_ download: WKDownload) {
        guard let target = exports.removeValue(forKey: ObjectIdentifier(download)) else { return }
        do {
            if target.replacing && FileManager.default.fileExists(atPath: target.destination.path) {
                _ = try FileManager.default.replaceItemAt(target.destination, withItemAt: target.temporary)
            } else {
                try FileManager.default.moveItem(at: target.temporary, to: target.destination)
            }
        } catch {
            try? FileManager.default.removeItem(at: target.temporary)
            showExportError(error)
        }
    }

    func download(_ download: WKDownload, didFailWithError error: Error, resumeData: Data?) {
        if let target = exports.removeValue(forKey: ObjectIdentifier(download)) { try? FileManager.default.removeItem(at: target.temporary) }
        guard (error as NSError).code != NSURLErrorCancelled else { return }
        showExportError(error)
    }

    func showExportError(_ error: Error) {
        let alert = NSAlert()
        alert.messageText = "导出失败"
        alert.informativeText = error.localizedDescription
        alert.beginSheetModal(for: window)
    }
}

@main
struct Main {
    @MainActor static func main() {
        let application = NSApplication.shared
        application.setActivationPolicy(.regular)
        let delegate = AppDelegate()
        application.delegate = delegate
        application.run()
    }
}
