# MeshCat Frontend

This is a separated frontend for the MeshCat URDF visualizer that connects to a WebSocket-only backend.

## Architecture

- **Backend**: WebSocket server on port 7000 (MeshCat ZMQ server)
- **Frontend**: Development server on port 3000 that connects to the WebSocket
- **Communication**: WebSocket protocol for real-time 3D scene updates

## Setup

1. Install dependencies:
```bash
npm install
```

2. Build the frontend:
```bash
npm run build
```

## Development

Start the development server:
```bash
npm start
```

This will start a development server on `http://localhost:3000` that connects to the MeshCat WebSocket server running on port 7002.

## Usage

1. Start the backend first:
```bash
python backends/meshcat_backend.py
```

2. Start the frontend:
```bash
cd frontends/meshcat
npm start
```

3. Open your browser to `http://localhost:3000`

The frontend will automatically connect to the WebSocket server running on port 7000 and display the robot visualization.

## Files Copied from external/meshcat

- `src/index.js` - Main MeshCat JavaScript library (75KB, 1927 lines)
- `package.json` - Dependencies and build configuration  
- `webpack.config.js` - Build and development server configuration

## Customizations

- Modified `index.html` to connect to port 7000 instead of default
- Added webpack-dev-server for development
- Updated package.json with development scripts
- Separated WebSocket server from static file serving

This separation allows for:
- Independent development of frontend and backend
- Custom frontend UI/UX without modifying the core MeshCat library
- Better development experience with hot reloading
- Ability to run frontend on different ports or hosts 