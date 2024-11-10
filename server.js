const express = require("express");
const { spawn } = require("child_process");

const app = express();

// Define the port where the server will run
const port = process.env.PORT || 3000;

// Start the Python bot
const startBot = () => {
  const pythonProcess = spawn("python", ["bot.py"]);

  pythonProcess.stdout.on("data", (data) => {
    console.log(`stdout: ${data}`);
  });

  pythonProcess.stderr.on("data", (data) => {
    console.error(`stderr: ${data}`);
  });

  pythonProcess.on("close", (code) => {
    console.log(`Python bot process exited with code ${code}`);
  });
};

// Simple route for keeping the server awake (if using free hosting)
app.get("/", (req, res) => {
  res.send("Bot is running!");
});

// Start the bot
startBot();

// Start the web server
app.listen(port, () => {
  console.log(`Server is running on port ${port}`);
});
