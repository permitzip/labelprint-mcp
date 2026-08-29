import Foundation
import IOBluetooth

/// Hex-line RFCOMM bridge for the Python client.
/// stdin:  `>aabbcc` send, `Q` quit
/// stdout: `<aabbcc` recv, `!ready`, `!error ...`

final class Bridge: NSObject, IOBluetoothRFCOMMChannelDelegate {
    let address: String
    var channel: IOBluetoothRFCOMMChannel?
    let out = FileHandle.standardOutput
    let err = FileHandle.standardError

    init(address: String) {
        self.address = address
    }

    func log(_ msg: String) {
        if let data = (msg + "\n").data(using: .utf8) {
            err.write(data)
        }
    }

    func emit(_ msg: String) {
        if let data = (msg + "\n").data(using: .utf8) {
            out.write(data)
        }
    }

    func start() -> Bool {
        guard let device = IOBluetoothDevice(addressString: address) else {
            emit("!error no device")
            return false
        }
        let conn = device.openConnection()
        log("openConnection=\(conn) connected=\(device.isConnected())")
        var ch: IOBluetoothRFCOMMChannel?
        let status = device.openRFCOMMChannelSync(&ch, withChannelID: 1, delegate: self)
        log("openRFCOMM ch1 status=\(status)")
        channel = ch
        if status != 0 || ch == nil {
            emit("!error rfcomm \(status)")
            return false
        }
        emit("!ready")
        return true
    }

    func rfcommChannelData(_ rfcommChannel: IOBluetoothRFCOMMChannel!, data dataPointer: UnsafeMutableRawPointer!, length dataLength: Int) {
        let bytes = Data(bytes: dataPointer, count: dataLength)
        emit("<" + bytes.map { String(format: "%02x", $0) }.joined())
    }

    func rfcommChannelClosed(_ rfcommChannel: IOBluetoothRFCOMMChannel!) {
        emit("!closed")
    }

    func send(hex: String) {
        guard let channel else {
            emit("!error no channel")
            return
        }
        var data = Data()
        var chars = Array(hex)
        if chars.count % 2 == 1 { chars.append("0") }
        var i = 0
        while i < chars.count {
            let byte = UInt8(String([chars[i], chars[i + 1]]), radix: 16) ?? 0
            data.append(byte)
            i += 2
        }
        var copy = data
        let rc = copy.withUnsafeMutableBytes { raw -> IOReturn in
            guard let ptr = raw.bindMemory(to: UInt8.self).baseAddress else { return 1 }
            return channel.writeSync(UnsafeMutableRawPointer(mutating: ptr), length: UInt16(data.count))
        }
        if rc != 0 {
            emit("!error write \(rc)")
        }
    }
}

let addr = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : ""
if addr.isEmpty {
    FileHandle.standardOutput.write(Data("!error missing address\n".utf8))
    exit(2)
}
let bridge = Bridge(address: addr)
if !bridge.start() {
    exit(2)
}

DispatchQueue.global(qos: .userInitiated).async {
    while true {
        guard let lineData = readLine(strippingNewline: true) else { break }
        if lineData == "Q" {
            bridge.channel?.close()
            exit(0)
        }
        if lineData.hasPrefix(">") {
            bridge.send(hex: String(lineData.dropFirst()))
        }
    }
    exit(0)
}

RunLoop.main.run()
