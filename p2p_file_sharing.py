import socket
import threading
import json
import os
import time
import argparse
import uuid
import hashlib
import sys
from pathlib import Path


class Peer:
    def __init__(self, host='0.0.0.0', port=8000, shared_dir='shared_files', 
                 bootstrap_nodes=None, verbose=False, peer_id=None):
        """Initialize the peer with host, port, shared directory and bootstrap nodes."""
        self.host = host
        self.port = port
        self.shared_dir = shared_dir
        
        # Use provided peer_id or load from file, or generate a new one
        self.id = self._get_or_create_peer_id(peer_id)
        
        self.peers = {}  # Dictionary to store known peers: {peer_id: (host, port)}
        self.files = {}  # Dictionary to store files: {filename: file_hash}
        self.running = False
        self.verbose = verbose
        self.log_lock = threading.Lock()  # Lock for synchronized console output
        self.bootstrap_nodes = bootstrap_nodes or []
        
        # Ensure the application directory exists
        self._ensure_app_dir_exists()
        
        # Make sure shared_dir is an absolute path
        self._ensure_absolute_path()
        
        # Create shared directory only if it doesn't exist
        if not os.path.exists(self.shared_dir):
            try:
                os.makedirs(self.shared_dir)
                self.log(f"Created shared directory: {self.shared_dir}")
            except Exception as e:
                self.log(f"Error creating shared directory: {e}", force=True)
        
        # Initialize server socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        # Get the assigned port if it was set to 0
        self.port = self.server_socket.getsockname()[1]
        
        # Get local IP for display
        self.local_ip = self.get_local_ip()
        
        # Scan for files in the shared directory
        self.scan_files()
    
    def _get_application_path(self):
        """Get the path to the application directory."""
        if getattr(sys, 'frozen', False):
            # If running as executable
            return os.path.dirname(sys.executable)
        else:
            # If running as script
            return os.path.dirname(os.path.abspath(__file__))
    
    def _ensure_app_dir_exists(self):
        """Ensure the application directory exists."""
        app_dir = os.path.join(self._get_application_path(), 'p2p_data')
        os.makedirs(app_dir, exist_ok=True)
        return app_dir
    
    def _ensure_absolute_path(self):
        """Convert shared_dir to absolute path if it's relative."""
        if not os.path.isabs(self.shared_dir):
            self.shared_dir = os.path.join(self._get_application_path(), self.shared_dir)
    
    def _get_or_create_peer_id(self, provided_id=None):
        """Get existing peer ID from file or create a new one."""
        if provided_id:
            return provided_id
        
        # Path to store the peer ID
        app_dir = os.path.join(self._get_application_path(), 'p2p_data')
        os.makedirs(app_dir, exist_ok=True)
        id_file = os.path.join(app_dir, 'peer_id.txt')
        
        # Check if peer ID already exists
        if os.path.exists(id_file):
            try:
                with open(id_file, 'r') as f:
                    peer_id = f.read().strip()
                    if peer_id:
                        return peer_id
            except:
                pass  # If reading fails, generate a new ID
        
        # Generate a new peer ID
        new_id = str(uuid.uuid4())[:8]
        
        # Save the ID to file
        try:
            with open(id_file, 'w') as f:
                f.write(new_id)
        except Exception as e:
            print(f"Warning: Could not save peer ID: {e}")
        
        return new_id
    
    @staticmethod
    def get_local_ip():
        """Get the local IP address of this machine."""
        try:
            # Create a socket to determine the local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Doesn't actually connect but helps determine the IP
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return '127.0.0.1'  # Default to localhost if unable to determine
    
    def log(self, message, force=False):
        """Thread-safe logging that doesn't interrupt user input."""
        if self.verbose or force:
            with self.log_lock:
                print(f"\r{message}{' ' * 20}")
                print(f"\n[Peer {self.id}] > ", end='', flush=True)
    
    def scan_files(self):
        """Scan the shared directory for files and update the files dictionary."""
        self.files = {}
        try:
            if not os.path.exists(self.shared_dir):
                self.log(f"Warning: Shared directory does not exist: {self.shared_dir}", force=True)
                return
                
            for file_path in Path(self.shared_dir).glob('*'):
                if file_path.is_file():
                    file_hash = self.calculate_file_hash(file_path)
                    self.files[file_path.name] = file_hash
        except Exception as e:
            self.log(f"Error scanning files: {e}", force=True)
            self.log(f"Shared directory path: {self.shared_dir}", force=True)
    
    @staticmethod
    def calculate_file_hash(file_path):
        """Calculate the SHA-256 hash of a file."""
        hash_obj = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()
    
    def start(self):
        """Start the peer server and announce presence."""
        if self.running:
            return
        
        self.running = True
        self.server_socket.listen(5)
        self.log(f"Peer {self.id} listening on {self.local_ip}:{self.port}", force=True)
        self.log(f"Connect other peers to this one using: --bootstrap {self.local_ip}:{self.port}", force=True)
        self.log(f"Shared directory: {self.shared_dir}", force=True)
        
        # Start server thread to accept connections
        server_thread = threading.Thread(target=self.accept_connections)
        server_thread.daemon = True
        server_thread.start()
        
        # Start discovery thread
        discovery_thread = threading.Thread(target=self.discover_peers)
        discovery_thread.daemon = True
        discovery_thread.start()
        
        # Start UI thread
        ui_thread = threading.Thread(target=self.user_interface)
        ui_thread.daemon = True
        ui_thread.start()
    
    def accept_connections(self):
        """Accept incoming connections from other peers."""
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                client_handler = threading.Thread(
                    target=self.handle_peer_connection,
                    args=(client_socket, address)
                )
                client_handler.daemon = True
                client_handler.start()
            except Exception as e:
                if self.running:
                    self.log(f"Error accepting connection: {e}")
    
    def handle_peer_connection(self, client_socket, address):
        """Handle an incoming connection from another peer."""
        try:
            # Receive message
            data = client_socket.recv(4096).decode('utf-8')
            if not data:
                return
            
            # Parse the message
            message = json.loads(data)
            message_type = message.get('type')
            
            if message_type == 'discovery':
                # Handle peer discovery
                peer_id = message.get('peer_id')
                peer_host = message.get('host', address[0])
                peer_port = message.get('port')
                
                # Add the peer to known peers
                if peer_id != self.id:
                    is_new = peer_id not in self.peers
                    self.peers[peer_id] = (peer_host, peer_port)
                    if is_new:
                        self.log(f"Discovered peer: {peer_id} at {peer_host}:{peer_port}")
                
                # Send response with our info and known peers
                response = {
                    'type': 'discovery_response',
                    'peer_id': self.id,
                    'host': self.local_ip,
                    'port': self.port,
                    'files': self.files,
                    'known_peers': {
                        pid: [host, port] for pid, (host, port) in self.peers.items()
                        if pid != peer_id and pid != self.id
                    }
                }
                client_socket.send(json.dumps(response).encode('utf-8'))
            
            elif message_type == 'discovery_response':
                # Handle discovery response
                peer_id = message.get('peer_id')
                peer_host = message.get('host', address[0])
                peer_port = message.get('port')
                peer_files = message.get('files', {})
                known_peers = message.get('known_peers', {})
                
                # Add the peer to known peers
                if peer_id != self.id:
                    is_new = peer_id not in self.peers
                    self.peers[peer_id] = (peer_host, peer_port)
                    if is_new:
                        self.log(f"Connected to peer: {peer_id} at {peer_host}:{peer_port}")
                        if peer_files:
                            self.log(f"Files available from {peer_id}:")
                            for filename in peer_files:
                                self.log(f"  - {filename}")
                
                # Add any new peers from the known_peers list
                for pid, (host, port) in known_peers.items():
                    if pid != self.id and pid not in self.peers:
                        self.peers[pid] = (host, port)
                        self.log(f"Learned about peer: {pid} at {host}:{port}")
            
            elif message_type == 'list_files':
                # Handle file listing request
                response = {
                    'type': 'file_list',
                    'peer_id': self.id,
                    'files': self.files
                }
                client_socket.send(json.dumps(response).encode('utf-8'))
            
            elif message_type == 'file_request':
                # Handle file request
                filename = message.get('filename')
                file_path = os.path.join(self.shared_dir, filename)
                
                if os.path.exists(file_path) and os.path.isfile(file_path):
                    # Send file metadata first
                    file_size = os.path.getsize(file_path)
                    metadata = {
                        'type': 'file_metadata',
                        'filename': filename,
                        'file_size': file_size
                    }
                    client_socket.send(json.dumps(metadata).encode('utf-8'))
                    
                    # Wait for acknowledgment
                    ack = client_socket.recv(1024).decode('utf-8')
                    if ack == 'ready':
                        # Send the file
                        with open(file_path, 'rb') as f:
                            while True:
                                file_data = f.read(4096)
                                if not file_data:
                                    break
                                client_socket.send(file_data)
                        self.log(f"File {filename} sent to {address}")
                else:
                    error = {
                        'type': 'error',
                        'message': f"File {filename} not found"
                    }
                    client_socket.send(json.dumps(error).encode('utf-8'))
        
        except Exception as e:
            self.log(f"Error handling connection: {e}")
        finally:
            client_socket.close()
    
    def discover_peers(self):
        """Discover other peers in the network."""
        # First, connect to bootstrap nodes if specified
        for node in self.bootstrap_nodes:
            try:
                host, port_str = node.split(':')
                port = int(port_str)
                self.log(f"Connecting to bootstrap node {host}:{port}")
                self.connect_to_peer(host, port)
            except Exception as e:
                self.log(f"Error connecting to bootstrap node {node}: {e}")
        
        known_peers = set()
        
        # Then periodically try to discover new peers
        while self.running:
            try:
                # Try to connect to known peers
                for peer_id, (host, port) in list(self.peers.items()):
                    # Skip if we already processed this peer recently
                    if peer_id in known_peers:
                        continue
                    
                    try:
                        # Add to known peers so we don't try again too soon
                        known_peers.add(peer_id)
                        self.connect_to_peer(host, port)
                    except Exception as e:
                        self.log(f"Error connecting to peer {peer_id} at {host}:{port}: {e}")
                
                # Reset known_peers set occasionally to allow reconnection attempts
                if len(known_peers) > 50:  # Arbitrary limit
                    known_peers = set()
                
                # Sleep before next discovery attempt
                time.sleep(10)
            except Exception as e:
                self.log(f"Error in peer discovery: {e}")
                time.sleep(10)
    
    def connect_to_peer(self, host, port):
        """Connect to a peer at the given host and port."""
        try:
            peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peer_socket.settimeout(3)
            peer_socket.connect((host, port))
            
            # Send discovery message
            discovery_msg = {
                'type': 'discovery',
                'peer_id': self.id,
                'host': self.local_ip,
                'port': self.port
            }
            peer_socket.send(json.dumps(discovery_msg).encode('utf-8'))
            
            # Receive response
            data = peer_socket.recv(4096).decode('utf-8')
            if data:
                self.handle_peer_connection(peer_socket, (host, port))
            peer_socket.close()
        except Exception as e:
            # Connection failed, handle silently
            pass
    
    def list_files_from_peer(self, peer_id):
        """Request file listing from a specific peer."""
        if peer_id not in self.peers:
            self.log(f"Peer {peer_id} not found", force=True)
            return
        
        peer_host, peer_port = self.peers[peer_id]
        try:
            peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peer_socket.settimeout(5)  # Increased timeout for network operations
            peer_socket.connect((peer_host, peer_port))
            
            # Send file list request
            request = {
                'type': 'list_files',
                'peer_id': self.id
            }
            peer_socket.send(json.dumps(request).encode('utf-8'))
            
            # Receive response
            data = peer_socket.recv(4096).decode('utf-8')
            response = json.loads(data)
            
            if response.get('type') == 'file_list':
                files = response.get('files', {})
                self.log(f"Files available from peer {peer_id}:", force=True)
                if files:
                    for filename in files:
                        self.log(f"  - {filename}", force=True)
                else:
                    self.log("  No files available", force=True)
                return files
            else:
                self.log("Invalid response received", force=True)
        except Exception as e:
            self.log(f"Error listing files from peer: {e}", force=True)
        finally:
            peer_socket.close()
    
    def download_file(self, peer_id, filename):
        """Download a file from a specific peer."""
        if peer_id not in self.peers:
            self.log(f"Peer {peer_id} not found", force=True)
            return
        
        peer_host, peer_port = self.peers[peer_id]
        try:
            peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peer_socket.settimeout(10)  # Increased timeout for file transfers
            peer_socket.connect((peer_host, peer_port))
            
            # Send file request
            request = {
                'type': 'file_request',
                'peer_id': self.id,
                'filename': filename
            }
            peer_socket.send(json.dumps(request).encode('utf-8'))
            
            # Receive file metadata
            data = peer_socket.recv(4096).decode('utf-8')
            metadata = json.loads(data)
            
            if metadata.get('type') == 'file_metadata':
                file_size = metadata.get('file_size', 0)
                self.log(f"Downloading {filename} ({file_size} bytes)...", force=True)
                
                # Send ready acknowledgment
                peer_socket.send('ready'.encode('utf-8'))
                
                # Ensure shared directory exists before downloading
                if not os.path.exists(self.shared_dir):
                    os.makedirs(self.shared_dir)
                
                # Receive and save the file
                file_path = os.path.join(self.shared_dir, filename)
                received = 0
                
                with open(file_path, 'wb') as f:
                    while received < file_size:
                        data = peer_socket.recv(4096)
                        if not data:
                            break
                        f.write(data)
                        received += len(data)
                        # Print progress occasionally
                        if received % (file_size // 10 or 4096) == 0:
                            progress = (received / file_size) * 100
                            self.log(f"Progress: {progress:.1f}%")
                
                self.log(f"File {filename} downloaded successfully", force=True)
                # Update file list
                self.scan_files()
            elif metadata.get('type') == 'error':
                self.log(f"Error: {metadata.get('message')}", force=True)
        except Exception as e:
            self.log(f"Error downloading file: {e}", force=True)
        finally:
            peer_socket.close()
    
    def user_interface(self):
        """Simple console-based user interface for interacting with the P2P network."""
        help_text = """
        Commands:
        - help: Show this help message
        - info: Display your peer ID and connection info
        - peers: List known peers
        - files: List local shared files
        - scan: Rescan shared directory for files
        - list <peer_id>: List files from a specific peer
        - download <peer_id> <filename>: Download a file from a peer
        - connect <host:port>: Connect to a specific peer
        - verbose [on|off]: Toggle verbose logging
        - exit: Exit the application
        """
        
        self.log(help_text, force=True)
        
        while self.running:
            try:
                command = input(f"\n[Peer {self.id}] > ")
                parts = command.strip().split()
                
                if not parts:
                    continue
                
                if parts[0] == 'help':
                    self.log(help_text, force=True)
                
                elif parts[0] == 'info':
                    self.log(f"Your peer ID: {self.id}", force=True)
                    self.log(f"You are listening on: {self.local_ip}:{self.port}", force=True)
                    self.log(f"Other peers can connect using: --bootstrap {self.local_ip}:{self.port}", force=True)
                    self.log(f"Shared directory: {self.shared_dir}", force=True)
                    self.log(f"Directory exists: {os.path.exists(self.shared_dir)}", force=True)
                
                elif parts[0] == 'peers':
                    if not self.peers:
                        self.log("No peers discovered yet", force=True)
                    else:
                        self.log("Known peers:", force=True)
                        for peer_id, (host, port) in self.peers.items():
                            self.log(f"  - {peer_id} at {host}:{port}", force=True)
                
                elif parts[0] == 'files':
                    if not os.path.exists(self.shared_dir):
                        self.log(f"Shared directory does not exist: {self.shared_dir}", force=True)
                    elif not self.files:
                        self.log("No files in shared directory", force=True)
                    else:
                        self.log("Shared files:", force=True)
                        for filename, file_hash in self.files.items():
                            self.log(f"  - {filename} ({file_hash[:8]}...)", force=True)
                
                elif parts[0] == 'scan':
                    if not os.path.exists(self.shared_dir):
                        self.log(f"Shared directory does not exist: {self.shared_dir}", force=True)
                        self.log("Create it? (y/n)", force=True)
                        create = input().strip().lower()
                        if create in ('y', 'yes'):
                            try:
                                os.makedirs(self.shared_dir)
                                self.log(f"Created shared directory: {self.shared_dir}", force=True)
                            except Exception as e:
                                self.log(f"Error creating directory: {e}", force=True)
                        else:
                            self.log("Skipping directory creation", force=True)
                            continue
                    
                    self.scan_files()
                    self.log("Shared directory scanned", force=True)
                    if self.files:
                        self.log("Files found:", force=True)
                        for filename in self.files:
                            self.log(f"  - {filename}", force=True)
                    else:
                        self.log("No files found in shared directory", force=True)
                
                elif parts[0] == 'list':
                    if len(parts) < 2:
                        self.log("Usage: list <peer_id>", force=True)
                    else:
                        self.list_files_from_peer(parts[1])
                
                elif parts[0] == 'download':
                    if len(parts) < 3:
                        self.log("Usage: download <peer_id> <filename>", force=True)
                    else:
                        self.download_file(parts[1], ' '.join(parts[2:]))
                
                elif parts[0] == 'connect':
                    if len(parts) < 2:
                        self.log("Usage: connect <host:port>", force=True)
                    else:
                        try:
                            host, port_str = parts[1].split(':')
                            port = int(port_str)
                            self.log(f"Connecting to {host}:{port}...", force=True)
                            self.connect_to_peer(host, port)
                            self.log("Connection attempt completed", force=True)
                        except Exception as e:
                            self.log(f"Error connecting to peer: {e}", force=True)
                
                elif parts[0] == 'verbose':
                    if len(parts) > 1:
                        if parts[1].lower() in ('on', 'true', '1', 'yes'):
                            self.verbose = True
                            self.log("Verbose logging enabled", force=True)
                        elif parts[1].lower() in ('off', 'false', '0', 'no'):
                            self.verbose = False
                            self.log("Verbose logging disabled", force=True)
                    else:
                        self.verbose = not self.verbose
                        self.log(f"Verbose logging {'enabled' if self.verbose else 'disabled'}", force=True)
                
                elif parts[0] == 'exit':
                    self.running = False
                    self.log("Exiting...", force=True)
                    break
                
                else:
                    self.log(f"Unknown command: {parts[0]}", force=True)
                    self.log("Type 'help' for available commands", force=True)
            except Exception as e:
                self.log(f"Error in command processing: {e}", force=True)
    
    def stop(self):
        """Stop the peer and close connections."""
        self.running = False
        self.server_socket.close()
        self.log(f"Peer {self.id} stopped", force=True)


def main():
    parser = argparse.ArgumentParser(description="P2P File Sharing Application")
    parser.add_argument('--host', default='0.0.0.0', help='Host address to bind to')
    parser.add_argument('--port', type=int, default=8000, help='Port to bind to')
    parser.add_argument('--dir', default='shared_files', help='Shared directory')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('--bootstrap', action='append', help='Bootstrap node (host:port)')
    parser.add_argument('--id', help='Set a specific peer ID (overrides saved ID)')
    args = parser.parse_args()
    
    bootstrap_nodes = args.bootstrap or []
    
    peer = Peer(host=args.host, port=args.port, shared_dir=args.dir, 
                bootstrap_nodes=bootstrap_nodes, verbose=args.verbose, peer_id=args.id)
    
    try:
        peer.start()
        # Keep the main thread alive
        while peer.running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        peer.stop()


if __name__ == "__main__":
    main()