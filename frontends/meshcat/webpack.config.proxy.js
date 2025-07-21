const path = require('path');

module.exports = {
  mode: 'development',
  entry: './src/index.js',
  output: {
    filename: 'bundle.js',
    path: path.resolve(__dirname, 'dist'),
    clean: true,
  },
  // devServer: {
  //   allowedHosts: 'all',
  //   static: [
  //     {
  //       directory: path.join(__dirname, 'dist'),
  //     },
  //     {
  //       directory: __dirname,
  //       publicPath: '/',
  //     }
  //   ],
  //   port: 3000,
  //   host: 'localhost',
  //   hot: true,
  //   historyApiFallback: {
  //     index: '/index.html'
  //   },
  //   // WebSocket proxy configuration
  //   proxy: [
  //     {
  //       context: ['/ws'],
  //       target: 'http://127.0.0.1:7000',  // Try HTTP target instead of WS
  //       ws: true,
  //       changeOrigin: true,
  //       logLevel: 'debug',
  //       secure: false,
  //       pathRewrite: {
  //         '^/ws': '' // Remove /ws prefix when forwarding to meshcat-server
  //       },
  //       // Try headers in different ways
  //       headers: {
  //         'host': '127.0.0.1:7000',
  //         'origin': 'http://127.0.0.1:7000',
  //         'connection': 'upgrade',
  //         'upgrade': 'websocket'
  //       },
  //       onProxyReqWs: (proxyReq, req, socket, options, head) => {
  //         // Remove problematic headers and set clean ones
  //         proxyReq.removeHeader('origin');
  //         proxyReq.removeHeader('host');
  //         proxyReq.setHeader('Host', '127.0.0.1:7000');
  //         proxyReq.setHeader('Origin', 'http://127.0.0.1:7000');
  //         proxyReq.setHeader('Sec-WebSocket-Version', '13');
  //       }
  //     }
  //   ],
  // },
  devServer: {
    static: path.join(__dirname, './'),
    port: 3000,
    hot: true,
    allowedHosts: 'all',
    historyApiFallback: {
      index: '/proxy-test.html'
    },
    proxy: [
      {
        context: ['/ws'],
        target: 'ws://127.0.0.1:7000',
        ws: true,
        changeOrigin: true,
        logLevel: 'debug',
        onProxyReqWs: (proxyReq) => {
          proxyReq.setHeader('Origin', 'http://127.0.0.1:7000');
        },
      },
    ],
  },
  module: {
    rules: [
      {
        test: /\.js$/,
        exclude: /node_modules/,
        use: {
          loader: 'babel-loader',
          options: {
            presets: ['@babel/preset-env']
          }
        }
      }
    ]
  },
  resolve: {
    extensions: ['.js'],
  },
};
