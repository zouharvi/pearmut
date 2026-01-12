const path = require('path');
const HtmlWebpackPlugin = require('html-webpack-plugin');
const CopyWebpackPlugin = require('copy-webpack-plugin');
const TerserPlugin = require("terser-webpack-plugin");
const MiniCssExtractPlugin = require("mini-css-extract-plugin");

// Change module.exports to an arrow function
module.exports = (env, argv) => {
  return {
    entry: {
      index: './src/index.ts',
      annotate: './src/annotate.ts',
      dashboard: './src/dashboard.ts',
    },
    output: {
      filename: '[name].bundle.js',
      path: path.resolve(__dirname, '../server/static'),
      clean: true,
    },
    optimization: {
      minimize: true,
      minimizer: [
        new TerserPlugin({
          extractComments: false,
          terserOptions: {
            format: {
              comments: false,
            },
          },
        }),
      ],
    },

    module: {
      rules: [
        {
          test: /\.ts$/,
          use: 'ts-loader',
          exclude: /node_modules/,
        },
        {
          test: /\.css$/,
          use: [MiniCssExtractPlugin.loader, "css-loader"],
        },
      ],
    },
    resolve: {
      extensions: ['.ts', '.js'],
    },
    plugins: [
      new MiniCssExtractPlugin({
        filename: "style.css",
      }),
      new HtmlWebpackPlugin({
        template: './src/index.html',
        filename: 'index.html',
        chunks: ['index'],
        hash: true,
      }),
      new HtmlWebpackPlugin({
        template: './src/annotate.html',
        filename: 'annotate.html',
        chunks: ['annotate'],
        hash: true,
      }),
      new HtmlWebpackPlugin({
        template: './src/dashboard.html',
        filename: 'dashboard.html',
        chunks: ['dashboard'],
        hash: true,
      }),
      new CopyWebpackPlugin({
        patterns: [
          { from: 'src/favicon.svg', to: '.' },
        ],
      }),
    ],
    devServer: {
      static: '../server/static',
      port: 8000,
      open: true,
    },
    // Set the mode based on the CLI argument
    mode: argv.mode || 'development',

    devtool: argv.mode === 'production' ? false : 'source-map',
  };
};