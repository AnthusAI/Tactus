"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode_1 = require("vscode");
const child_process_1 = require("child_process");
const node_1 = require("vscode-languageclient/node");
let client;
/**
 * Auto-detect Python installation.
 * Tries common Python commands in order of preference.
 */
async function findPython() {
    const candidates = [
        'python3',
        'python',
        'python3.12',
        'python3.11',
        'python3.10',
        'python3.9'
    ];
    for (const cmd of candidates) {
        try {
            (0, child_process_1.execSync)(`${cmd} --version`, { stdio: 'ignore' });
            return cmd;
        }
        catch {
            // Command not found, try next
        }
    }
    throw new Error('Python not found. Please install Python 3.9 or higher.');
}
/**
 * Check if tactus-lsp-server is installed.
 */
async function checkLSPServer(pythonCmd) {
    try {
        (0, child_process_1.execSync)(`${pythonCmd} -c "import tactus_lsp_server"`, { stdio: 'ignore' });
        return true;
    }
    catch {
        return false;
    }
}
async function activate(context) {
    // Find Python
    let pythonCommand;
    try {
        pythonCommand = await findPython();
    }
    catch (error) {
        vscode_1.window.showErrorMessage('Tactus: Python not found. Please install Python 3.9+ to use LSP features. ' +
            'Syntax highlighting will still work without Python.');
        return;
    }
    // Check if LSP server is installed
    const hasLSP = await checkLSPServer(pythonCommand);
    if (!hasLSP) {
        const answer = await vscode_1.window.showWarningMessage('Tactus LSP Server not found. Install it for enhanced features like ' +
            'validation, completions, and semantic highlighting.', 'Install Now', 'Later');
        if (answer === 'Install Now') {
            const terminal = vscode_1.window.createTerminal('Tactus LSP Install');
            terminal.show();
            terminal.sendText(`pip install tactus-lsp-server`);
        }
        return;
    }
    // Configure LSP server options
    const serverOptions = {
        command: pythonCommand,
        args: ['-m', 'tactus_lsp_server.stdio_server'],
        transport: node_1.TransportKind.stdio,
        options: {
            env: { ...process.env, PYTHONUNBUFFERED: '1' }
        }
    };
    // Configure language client options
    const clientOptions = {
        documentSelector: [{ scheme: 'file', language: 'tactus' }],
        synchronize: {
            // Notify server about .tac file changes
            fileEvents: vscode_1.workspace.createFileSystemWatcher('**/*.tac')
        }
    };
    // Create language client
    client = new node_1.LanguageClient('tactusLanguageServer', 'Tactus Language Server', serverOptions, clientOptions);
    // Start the client (this also starts the server)
    try {
        await client.start();
        vscode_1.window.showInformationMessage('Tactus LSP Server started successfully!');
    }
    catch (error) {
        vscode_1.window.showErrorMessage(`Failed to start Tactus LSP Server: ${error}. ` +
            'Syntax highlighting will still work.');
    }
}
async function deactivate() {
    if (!client) {
        return undefined;
    }
    return client.stop();
}
//# sourceMappingURL=extension.js.map