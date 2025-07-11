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
    watch: true,
    mode: "development",
    devtool: "eval-cheap-source-map",
    devServer: {
        static: {
            directory: path.join(__dirname, './'),
        },
        compress: true,
        port: 3000,
        hot: true,
        open: true
    }
}, {
    entry: './src/index.js',
    output: {
        filename: "main.min.js",
        library: "MeshCat",
        libraryTarget: 'umd',
        path: path.resolve(__dirname, 'dist')
    },
    watch: true,
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
