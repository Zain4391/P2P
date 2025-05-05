# Decentralized P2P File Sharing

A fully decentralized peer-to-peer file sharing application that enables direct file transfer between peers without relying on a central server.

## Features

- **True Decentralization**: No central server required for operation
- **Cross-Platform Support**: Works on Windows, Linux, and macOS
- **Persistent Peer IDs**: Maintains consistent peer identity across sessions
- **Direct File Transfer**: Files transfer directly between peers
- **Automatic Peer Discovery**: Finds other peers on the network automatically
- **Bootstrap Mechanism**: Easy network entry via existing peers
- **File Integrity**: SHA-256 hash verification of shared files
- **User-Friendly CLI**: Simple command interface for all operations

## Screenshots

[Screenshots would go here]

## Requirements

- Python 3.6 or higher

## Installation

### Option 1: Run from Source

1. Clone this repository:
   ```bash
   git clone https://github.com/Zain4391/P2P.git
   cd P2P
   ```

2. Run the application:
   ```bash
   python p2p_file_sharing.py
   ```

### Option 2: Use Pre-built Executables

Download the appropriate executable for your platform from the Releases section.

## Usage

### Starting a New P2P Network

```bash
# On Linux/macOS
./p2p_file_sharing --port 8001 --dir ./shared_files

# On Windows
p2p_file_sharing.exe --port 8001 --dir .\shared_files
```

### Joining an Existing Network

```bash
# On Linux/macOS
./p2p_file_sharing --port 8002 --dir ./shared_files --bootstrap 192.168.1.100:8001

# On Windows
p2p_file_sharing.exe --port 8002 --dir .\shared_files --bootstrap 192.168.1.100:8001
```

Replace `192.168.1.100:8001` with the IP and port of a known peer.

### Command-Line Arguments

- `--host`: Host address to bind to (default: 0.0.0.0)
- `--port`: Port to bind to (default: 8000)
- `--dir`: Directory to share and store downloaded files (default: shared_files)
- `--verbose`: Enable verbose logging
- `--bootstrap`: Bootstrap node to connect to (format: host:port)
- `--id`: Set a specific peer ID (overrides saved ID)

### Interactive Commands

Once running, use these commands to interact with the network:

- `help`: Show the help message
- `info`: Display your peer ID and connection information
- `peers`: List discovered peers
- `files`: List files in your shared directory
- `scan`: Rescan the shared directory for new files
- `list <peer_id>`: List files available from a specific peer
- `download <peer_id> <filename>`: Download a file from a peer
- `connect <host:port>`: Manually connect to a peer
- `verbose [on|off]`: Toggle verbose logging
- `exit`: Exit the application

## Building Executables

You can build standalone executables for distribution:

### On Windows

```cmd
pip install pyinstaller
pyinstaller --onefile p2p_file_sharing.py
```

### On Linux/macOS

```bash
pip install pyinstaller
pyinstaller --onefile p2p_file_sharing.py
```

The executable will be created in the `dist` directory.

## Network Considerations

- The application works best on local networks
- For connections across the internet, port forwarding may be required
- Firewalls might block connections; ensure the chosen port is open

## How It Works

1. **Peer Discovery**: Peers find each other through bootstrap nodes or manual connections
2. **File Indexing**: Each peer maintains a list of available files and their hashes
3. **Direct Transfer**: Files transfer directly between peers over TCP sockets
4. **Persistence**: Peer IDs are stored locally for consistent network identity

## Technical Details

- **Network Protocol**: Custom TCP-based protocol for peer communication and file transfer
- **Data Format**: JSON for peer metadata and control messages, raw binary for file transfers
- **File Verification**: SHA-256 hashing ensures file integrity
- **Threading Model**: Multi-threaded design separates UI, server, and discovery operations

## Limitations

- No encryption for data transfers
- No NAT traversal capabilities (may require port forwarding)
- Basic command-line interface
- No search functionality across the network

## Future Improvements

- [ ] Add encryption for secure file transfers
- [ ] Implement NAT traversal for better connectivity
- [ ] Add file searching across the network
- [ ] Develop a web UI using Flask
- [ ] Add parallel downloads from multiple sources
- [ ] Implement a distributed hash table (DHT) for better peer discovery

## License

MIT

## Acknowledgments

- This project was developed as a Computer Networks course project
- Inspired by decentralized systems like BitTorrent and IPFS