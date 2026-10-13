import AppKit
import ApplicationServices
import CoreGraphics
import Vision

struct BridgeFailure: Error { let message: String }

func fail(_ message: String) throws -> Never { throw BridgeFailure(message: message) }

func windows() -> [[String: Any]] {
    let all = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] ?? []
    return all.filter { w in
        guard w[kCGWindowOwnerName as String] as? String == "ArcTime Pro",
              let pid = w[kCGWindowOwnerPID as String] as? Int,
              let app = NSRunningApplication(processIdentifier: pid_t(pid)),
              let path = app.executableURL?.path else { return false }
        return path.contains("/ArcTime Pro.app/")
    }
}

func geometry(_ w: [String: Any]) throws -> CGRect {
    guard let bounds = w[kCGWindowBounds as String] as? [String: Any],
          let frame = CGRect(dictionaryRepresentation: bounds as CFDictionary) else { try fail("invalid_window") }
    return frame
}

func text(_ w: [String: Any]) throws -> [[String: Any]] {
    let file = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString + ".png")
    defer { try? FileManager.default.removeItem(at: file) }
    let task = Process()
    task.executableURL = URL(fileURLWithPath: "/usr/sbin/screencapture")
    task.arguments = ["-x", "-o", "-l", String(w[kCGWindowNumber as String] as? Int ?? 0), file.path]
    task.standardError = FileHandle.nullDevice
    try task.run()
    task.waitUntilExit()
    guard task.terminationStatus == 0, let image = NSImage(contentsOf: file),
          let cg = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else { try fail("screen_capture_required") }
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["zh-Hans", "en-US"]
    request.usesLanguageCorrection = false
    try VNImageRequestHandler(cgImage: cg).perform([request])
    return (request.results ?? []).compactMap { observation in
        guard let candidate = observation.topCandidates(1).first else { return nil }
        let b = observation.boundingBox
        return ["text": candidate.string, "x": b.midX, "y": 1 - b.midY]
    }
}

func target(_ id: String, _ title: String) throws -> [String: Any] {
    guard let window = windows().first(where: { String($0[kCGWindowNumber as String] as? Int ?? -1) == id }),
          window[kCGWindowName as String] as? String == title else { try fail("window_changed") }
    return window
}

func activate(_ w: [String: Any]) throws -> pid_t {
    guard AXIsProcessTrusted(), let id = w[kCGWindowOwnerPID as String] as? Int,
          let app = NSRunningApplication(processIdentifier: pid_t(id)) else { try fail("accessibility_required") }
    app.activate(options: [])
    Thread.sleep(forTimeInterval: 0.2)
    guard app.isActive else { try fail("focus_changed") }
    return pid_t(id)
}

func key(_ code: CGKeyCode, _ flags: CGEventFlags) throws {
    guard let down = CGEvent(keyboardEventSource: nil, virtualKey: code, keyDown: true),
          let up = CGEvent(keyboardEventSource: nil, virtualKey: code, keyDown: false) else { try fail("event_failed") }
    down.flags = flags
    up.flags = flags
    down.post(tap: .cghidEventTap)
    up.post(tap: .cghidEventTap)
}

func run(_ args: [String]) throws -> [String: Any] {
    guard let action = args.first else { try fail("missing_action") }
    if action == "inspect" {
        var result: [[String: Any]] = []
        for w in windows() {
            let frame = try geometry(w)
            if frame.width < 100 || frame.height < 50 { continue }
            result.append(["id": w[kCGWindowNumber as String] ?? 0,
                           "title": w[kCGWindowName as String] ?? "",
                           "width": frame.width, "height": frame.height, "texts": try text(w)])
        }
        return ["windows": result, "accessibility": AXIsProcessTrusted(), "screen_capture": CGPreflightScreenCaptureAccess()]
    }
    guard args.count >= 3 else { try fail("missing_target") }
    let w = try target(args[1], args[2])
    _ = try activate(w)
    if action == "key" {
        guard args.count == 5, let code = UInt16(args[3]), ["cmd", "cmdshift", "none"].contains(args[4]) else { try fail("invalid_key") }
        var flags: CGEventFlags = []
        if args[4].hasPrefix("cmd") { flags.insert(.maskCommand) }
        if args[4] == "cmdshift" { flags.insert(.maskShift) }
        try key(code, flags)
    } else if action == "text" {
        guard args.count == 4 else { try fail("invalid_text") }
        let clipboard = NSPasteboard.general
        let previous = (clipboard.pasteboardItems ?? []).map { item -> NSPasteboardItem in
            let saved = NSPasteboardItem()
            for type in item.types { if let data = item.data(forType: type) { saved.setData(data, forType: type) } }
            return saved
        }
        clipboard.clearContents()
        clipboard.setString(args[3], forType: .string)
        let changeCount = clipboard.changeCount
        defer {
            if clipboard.changeCount == changeCount {
                clipboard.clearContents()
                clipboard.writeObjects(previous)
            }
        }
        try key(0, .maskCommand)
        try key(9, .maskCommand)
        Thread.sleep(forTimeInterval: 0.3)
    } else if action == "click" || action == "point" {
        var x: Double
        var y: Double
        if action == "click" {
            guard args.count == 4 else { try fail("missing_label") }
            let matches = try text(w).filter { $0["text"] as? String == args[3] }
            guard matches.count == 1, let hit = matches.first, let hx = hit["x"] as? Double, let hy = hit["y"] as? Double else { try fail("ambiguous_button") }
            x = hx; y = hy
        } else {
            guard args.count == 5, let px = Double(args[3]), let py = Double(args[4]), (0...1).contains(px), (0...1).contains(py) else { try fail("invalid_point") }
            x = px; y = py
        }
        let frame = try geometry(w)
        let position = CGPoint(x: frame.minX + frame.width * x, y: frame.minY + frame.height * y)
        guard let down = CGEvent(mouseEventSource: nil, mouseType: .leftMouseDown, mouseCursorPosition: position, mouseButton: .left),
              let up = CGEvent(mouseEventSource: nil, mouseType: .leftMouseUp, mouseCursorPosition: position, mouseButton: .left) else { try fail("event_failed") }
        guard NSRunningApplication(processIdentifier: pid_t(w[kCGWindowOwnerPID as String] as? Int ?? -1))?.isActive == true else { try fail("focus_changed") }
        down.post(tap: .cghidEventTap); up.post(tap: .cghidEventTap)
    } else { try fail("unknown_action") }
    return ["ok": true]
}

do {
    let result = try run(Array(CommandLine.arguments.dropFirst()))
    let data = try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys])
    print(String(decoding: data, as: UTF8.self))
} catch {
    let message = (error as? BridgeFailure)?.message ?? "native_bridge_failed"
    let data = try! JSONSerialization.data(withJSONObject: ["error": message])
    print(String(decoding: data, as: UTF8.self))
    exit(1)
}
