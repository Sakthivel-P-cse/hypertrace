const express = require("express");
const app = express();
const port = 3000;

app.get("/", (req, res) => {
    res.send("Welcome to my website!");
});

app.get("/login", (req, res) => {
    // Simulate some work
    setTimeout(() => {
        res.json({ status: "success", user: "guest" });
    }, 100);
});

app.get("/error", (req, res) => {
    res.status(500).send("Something went wrong!");
});

app.listen(port, () => {
    console.log(`Website listening at http://localhost:${port}`);
});
