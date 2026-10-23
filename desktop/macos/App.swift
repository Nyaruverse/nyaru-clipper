import AppKit
import WebKit

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate, WKNavigationDelegate, WKDownloadDelegate, WKUIDelegate {
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
    var quitAuthorized = false
    var quitRequest: UUID?
    var exports: [ObjectIdentifier: (temporary: URL, destination: URL, replacing: Bool)] = [:]

    func applicationDidFinishLaunching(_ notification: Notification) {
        let mainMenu = NSMenu()
        let appItem = NSMenuItem()
        mainMenu.addItem(appItem)
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "设置…", action: #selector(openSettings(_:)), keyEquivalent: ",")
        appMenu.addItem(.separator())
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
        window.delegate = self
        window.minSize = NSSize(width: 760, height: 560)
        web = WKWebView(frame: window.contentView!.bounds)
        web.autoresizingMask = [.width, .height]
        web.navigationDelegate = self
        web.uiDelegate = self
        window.contentView = web
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        web.loadHTMLString("<html lang='zh-CN'><body style='font:16px -apple-system;padding:48px;background:#f3f5f7;color:#20292e'><h1 style='font-size:24px'>Nyaru Clipper</h1><p>正在启动本地工作台…</p><p style='color:#58666e'>首次启动需要准备语音模型，请稍候。</p></body></html>", baseURL: nil)
        do {
            let arguments = CommandLine.arguments
            func option(_ name: String) throws -> String? {
                guard let index = arguments.firstIndex(of: name) else { return nil }
                guard index + 1 < arguments.count, arguments[index + 1].hasPrefix("/") else {
                    throw NSError(domain: "NyaruStartup", code: 1, userInfo: [NSLocalizedDescriptionKey: "启动参数需要绝对路径：\(name)"])
                }
                return arguments[index + 1]
            }
            let runtime = try option("--unified-runtime")
            let guardRecipe = try option("--migration-guard")
            let data = runtime.map { URL(fileURLWithPath: $0).deletingLastPathComponent() }
                ?? FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("Nyaru Clipper", isDirectory: true)
            try FileManager.default.createDirectory(at: data, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
            ready = data.appendingPathComponent("startup-\(UUID().uuidString).json")
            let logURL = data.appendingPathComponent("app.log")
            if !FileManager.default.fileExists(atPath: logURL.path) {
                FileManager.default.createFile(atPath: logURL.path, contents: nil)
            }
            log = try FileHandle(forWritingTo: logURL)
            try log?.seekToEnd()
            let process = Process()
            process.executableURL = Bundle.main.resourceURL!.appendingPathComponent("runtime/nyaru-backend/nyaru-backend")
            process.arguments = ["--data", data.path, "--ready", ready.path, "--parent-pid", String(getpid())]
            if let runtime { process.arguments?.append(contentsOf: ["--unified-runtime", runtime]) }
            if let guardRecipe { process.arguments?.append(contentsOf: ["--migration-guard", guardRecipe]) }
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

    @objc func openSettings(_ sender: Any?) {
        web.evaluateJavaScript("window.dispatchEvent(new Event('nyaru-open-settings'))", completionHandler: nil)
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

    func windowShouldClose(_ sender: NSWindow) -> Bool {
        NSApp.terminate(nil)
        return false
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        if quitting { return .terminateLater }
        if !quitAuthorized, origin != nil {
            if quitRequest == nil { negotiateQuit() }
            return .terminateCancel
        }
        quitting = true
        timer?.invalidate()
        guard let process = helper, process.isRunning else { return .terminateNow }
        let pid = process.processIdentifier
        if kill(-pid, SIGTERM) != 0 { process.terminate() }
        waitForHelper(process)
        return .terminateLater
    }

    func waitForHelper(_ process: Process) {
        DispatchQueue.global().async {
            let deadline = Date().addingTimeInterval(20)
            while process.isRunning && Date() < deadline { Thread.sleep(forTimeInterval: 0.2) }
            DispatchQueue.main.async {
                guard process.isRunning else { NSApp.reply(toApplicationShouldTerminate: true); return }
                let alert = NSAlert()
                alert.messageText = "本地服务仍在结束当前操作"
                alert.informativeText = "继续等待可保留正常收尾。强制退出会中断未完成的操作；下次启动时将核对已发布结果。"
                alert.addButton(withTitle: "继续等待")
                alert.addButton(withTitle: "强制退出").hasDestructiveAction = true
                alert.beginSheetModal(for: self.window) { response in
                    if response == .alertSecondButtonReturn {
                        DispatchQueue.global().async {
                            kill(-process.processIdentifier, SIGKILL)
                            process.waitUntilExit()
                            DispatchQueue.main.async { NSApp.reply(toApplicationShouldTerminate: true) }
                        }
                    } else { self.waitForHelper(process) }
                }
            }
        }
    }

    func quitBridge(_ script: String, completion: @escaping (Result<Any, Error>) -> Void) {
        guard let origin, let current = web.url,
              current.scheme == origin.scheme, current.host == origin.host, current.port == origin.port else {
            completion(.failure(NSError(domain: "NyaruQuit", code: 1, userInfo: [NSLocalizedDescriptionKey: "编辑器尚未就绪；请稍后重试，或明确放弃修改退出"])))
            return
        }
        web.callAsyncJavaScript(script, arguments: [:], in: nil, in: .page) { [weak self] result in
            guard let self, self.web.url == current else {
                completion(.failure(NSError(domain: "NyaruQuit", code: 2, userInfo: [NSLocalizedDescriptionKey: "编辑器已切换，请重试"])))
                return
            }
            completion(result)
        }
    }

    func negotiateQuit() {
        let request = UUID()
        quitRequest = request
        quitBridge("return window.nyaruQuit?.status();") { [weak self] result in
            guard let self, self.quitRequest == request else { return }
            if case .success(let value) = result, value as? String == "clean" { self.authorizeQuit(); return }
            let alert = NSAlert()
            alert.messageText = "退出前保存修改？"
            alert.informativeText = "将保存所有任务的字幕编辑稿。保存失败会保留窗口和修改；默认设置需先在设置中保存。"
            if case .failure(let error) = result { alert.informativeText = error.localizedDescription }
            else if case .success(let value) = result, value as? String != "dirty" { alert.informativeText = "无法确认编辑器状态。请取消后重试；放弃修改将直接退出。" }
            alert.addButton(withTitle: "保存并退出")
            alert.addButton(withTitle: "取消")
            alert.addButton(withTitle: "放弃修改并退出").hasDestructiveAction = true
            alert.beginSheetModal(for: self.window) { response in
                guard self.quitRequest == request else { return }
                if response == .alertThirdButtonReturn { self.authorizeQuit() }
                else if response == .alertFirstButtonReturn { self.saveAndQuit(request) }
                else { self.quitRequest = nil }
            }
        }
    }

    func saveAndQuit(_ request: UUID) {
        let progress = NSAlert()
        progress.messageText = "正在保存字幕…"
        progress.informativeText = "等待所有任务保存完成后退出。取消会保留窗口，已提交的保存仍会完成。"
        progress.addButton(withTitle: "取消退出")
        progress.beginSheetModal(for: window) { _ in
            if self.quitRequest == request { self.quitRequest = nil }
        }
        quitBridge("const bridge = window.nyaruQuit; if (!bridge) return {saved: false, error: '编辑器尚未就绪，请取消后重试'}; const error = await bridge.save(); return {saved: error === null && bridge === window.nyaruQuit && bridge.status() === 'clean', error: error ?? '仍有未保存的修改，请重试'};") { [weak self] result in
            guard let self, self.quitRequest == request else { return }
            self.quitRequest = nil
            self.window.endSheet(progress.window)
            if case .success(let value) = result, let reply = value as? [String: Any], reply["saved"] as? Bool == true { self.authorizeQuit(); return }
            let alert = NSAlert()
            alert.messageText = "未退出：修改已保留"
            switch result {
            case .success(let value): alert.informativeText = (value as? [String: Any])?["error"] as? String ?? "无法确认保存结果，请重试"
            case .failure(let error): alert.informativeText = error.localizedDescription
            }
            alert.addButton(withTitle: "返回编辑")
            alert.beginSheetModal(for: self.window)
        }
    }

    func authorizeQuit() {
        quitRequest = nil
        quitAuthorized = true
        NSApp.terminate(nil)
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
