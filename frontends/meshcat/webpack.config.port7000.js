const LicensePlugin = require('webpack-license-plugin')
const path = require('path')

module.exports = [{
    entry: './src/index.js',
    output: {
        library: "MeshCat",
        libraryTarget: 'umd',
        path: path.resolve(__dirname, 'dist'),
        filename: 'main.js'
    },
    mode: "development",
    devtool: "eval-cheap-source-map",
    devServer: {
        static: {
            directory: path.join(__dirname, './'),
        },
        compress: true,
        port: 5000, // Use different port to avoid conflict with MeshCat backend
        hot: true,
        open: true,
        // Proxy WebSocket connections to the MeshCat backend
        proxy: [
            {
                context: ['/ws'],
                target: 'http://127.0.0.1:7000',
                ws: true,
                changeOrigin: true
            }
        ]
    }
}, {
    entry: './src/index.js',
    output: {
        filename: "main.min.js",
        library: "MeshCat",
        libraryTarget: 'umd',
        path: path.resolve(__dirname, 'dist')
    },
    mode: "production",
    module: {
      rules: [
        {
          test: /\/libs\/(basis|draco)\//,
          type: 'asset/inline'
        }
      ]
    },
    plugins: [
      new LicensePlugin({
        outputFilename: "main.min.js.THIRD_PARTY_LICENSES.json",
        licenseOverrides: {
          'wwobjloader2@6.2.1': 'MIT',
        }
      })
    ],
}];
