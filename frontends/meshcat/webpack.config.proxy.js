const path = require('path');

module.exports = {
  mode: 'development',
  entry: './src/index.js',
  output: {
    filename: 'bundle.js',
    path: path.resolve(__dirname, 'dist'),
    clean: true,
  },
  devServer: {
    static: [
      {
        directory: path.join(__dirname, 'dist'),
      },
      {
        directory: __dirname,
        publicPath: '/',
      }
    ],
    port: 3000,
    host: 'localhost',
    hot: true,
    historyApiFallback: {
      index: '/index.html'
    },
    // WebSocket proxy configuration
    proxy: [
      {
        context: ['/ws'],
        target: 'ws://127.0.0.1:7000',
        ws: true,
        changeOrigin: true,
        logLevel: 'debug',
      }
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
