const express = require("express");
const cors = require("cors");
const mysql = require("mysql2");
const jwt = require("jsonwebtoken");
const bcrypt = require("bcryptjs");
const { spawn } = require("child_process");
const cron = require("node-cron");
require("dotenv").config();

const app = express();
app.use(cors({ origin: "http://localhost:3000" }));
app.use(express.json());

const nodemailer = require("nodemailer");
const crypto = require("crypto");

const db = mysql.createConnection({
  host: process.env.DB_HOST,
  user: process.env.DB_USER,
  password: process.env.DB_PASS,
  database: process.env.DB_NAME,
});

db.connect((err) => {
  if (err) {
    console.error("MySQL connection error:", err);
    process.exit(1);
  }
  console.log("MySQL Connected");
});

const authenticate = (req, res, next) => {
  const token = req.headers.authorization?.split(" ")[1];
  if (!token) return res.status(401).json({ message: "Unauthorized" });
  jwt.verify(token, process.env.JWT_SECRET, (err, user) => {
    if (err) return res.status(403).json({ message: "Invalid token" });
    req.user = user;
    next();
  });
};
// Nodemailer transporter
const transporter = nodemailer.createTransport({
  host: process.env.SMTP_HOST,
  port: Number(process.env.SMTP_PORT || 587),
  secure: Number(process.env.SMTP_PORT) === 465, // true for 465, false otherwise
  auth: {
    user: process.env.SMTP_USER,
    pass: process.env.SMTP_PASS,
  },
  logger: !!process.env.SMTP_DEBUG, // <- verbose console logs
  debug: !!process.env.SMTP_DEBUG, // <- verbose SMTP transcript
});

// Optional: verify SMTP on boot
transporter.verify((err) => {
  if (err) console.error("SMTP connection error:", err.message);
  else console.log("SMTP server is ready to send mail");
});

// Helper to send reset email
async function sendResetEmail(to, resetUrl) {
  const appName = "HabitBuilder"; // or your app name
  const html = `
    <div style="font-family:Arial,Helvetica,sans-serif;max-width:520px;margin:0 auto;padding:24px;background:#fff;border:1px solid #eee;border-radius:12px">
      <h2 style="margin:0 0 12px;color:#31326F">${appName} – Password Reset</h2>
      <p style="margin:0 0 12px;color:#374151">Click the button below to choose a new password.</p>
      <p style="margin:0 0 12px;color:#374151"><strong>This link expires in 1 hour.</strong></p>
      <div style="margin:20px 0;">
        <a href="${resetUrl}" style="display:inline-block;background:#31326F;color:#fff;text-decoration:none;padding:12px 18px;border-radius:8px">Reset Password</a>
      </div>
      <p style="margin:12px 0;color:#6B7280">If you didn’t request this, you can ignore this email.</p>
      <hr style="border:none;border-top:1px solid #eee;margin:20px 0" />
      <p style="font-size:12px;color:#9CA3AF">If the button doesn’t work, paste this link in your browser:</p>
      <p style="font-size:12px;color:#2563EB;word-break:break-all;">${resetUrl}</p>
    </div>
  `;

  try {
    console.log(
      `[mail] sending reset to ${to} via ${process.env.SMTP_HOST}:${
        process.env.SMTP_PORT
      } (from=${process.env.SMTP_FROM || process.env.SMTP_USER})`
    );

    const info = await transporter.sendMail({
      from: process.env.SMTP_FROM || process.env.SMTP_USER,
      to,
      subject: `${appName}: Reset your password`,
      text: `Reset your password: ${resetUrl}\nThis link will expire in 1 hour.`,
      html,
    });

    console.log("[mail] sent OK. messageId:", info.messageId);
    if (info.response) console.log("[mail] SMTP response:", info.response);
    return info; // optional, useful for tests
  } catch (err) {
    console.error("[mail] send error:", err && err.message ? err.message : err);
    throw err; // let the caller handle the generic response
  }
}
app.post("/api/auth/forgot-password", (req, res) => {
  const { email } = req.body;
  console.log("[forgot] incoming request for:", email); // 👈 add

  if (!email) return res.status(400).json({ message: "Email is required" });

  const genericResponse = {
    message: "If that email exists, a reset link has been sent.",
  };

  db.query(
    "SELECT user_id, email FROM user WHERE email = ?",
    [email],
    (err, rows) => {
      if (err) {
        console.error("[forgot] lookup error:", err);
        return res.status(200).json(genericResponse);
      }

      if (!rows.length) {
        console.log("[forgot] user not found (generic reply).");
        return res.status(200).json(genericResponse);
      }

      const userId = rows[0].user_id;
      const token = crypto.randomBytes(32).toString("hex");
      const expires = new Date(Date.now() + 1000 * 60 * 60); // 1h

      db.query(
        "UPDATE user SET reset_token = ?, reset_expires = ? WHERE user_id = ?",
        [token, expires, userId],
        async (uerr) => {
          if (uerr) {
            console.error("[forgot] store token error:", uerr);
            return res.status(200).json(genericResponse);
          }

          const base = process.env.APP_URL || "http://localhost:3000";
          const resetUrl = `${base}/reset-password?token=${token}`;
          console.log("[forgot] token saved, resetUrl:", resetUrl); // 👈 add

          try {
            const info = await sendResetEmail(email, resetUrl);
            console.log("[forgot] sendMail OK:", info?.messageId); // 👈 add
          } catch (mailErr) {
            console.error(
              "[forgot] sendMail error:",
              mailErr?.message || mailErr
            );
          }

          if (process.env.NODE_ENV !== "production") {
            return res.json({ ...genericResponse, resetUrl }); // dev helper
          }
          return res.json(genericResponse);
        }
      );
    }
  );
});

// Auth Routes
app.post("/api/auth/register", async (req, res) => {
  const { f_name, l_name, email, password, dob, gender, user_role } = req.body;
  if (
    !f_name ||
    !l_name ||
    !email ||
    !password ||
    !dob ||
    !gender ||
    !user_role
  ) {
    return res.status(400).json({ message: "All fields are required" });
  }
  const hashedPass = await bcrypt.hash(password, 10);
  db.query(
    "INSERT INTO user (f_name, l_name, email, password, dob, gender, user_role, created_date) VALUES (?, ?, ?, ?, ?, ?, ?, NOW())",
    [f_name, l_name, email, hashedPass, dob, gender, user_role],
    (err) => {
      if (err) {
        console.error("Registration error:", err);
        return res
          .status(500)
          .json({ message: "Error registering", error: err.message });
      }
      res.status(201).json({ message: "User registered" });
    }
  );
});

app.post("/api/auth/login", (req, res) => {
  const { email, password } = req.body;
  if (!email || !password) {
    return res.status(400).json({ message: "Email and password are required" });
  }
  db.query(
    "SELECT * FROM user WHERE email = ?",
    [email],
    async (err, results) => {
      if (
        err ||
        !results.length ||
        !(await bcrypt.compare(password, results[0].password))
      ) {
        return res.status(401).json({ message: "Invalid credentials" });
      }
      const token = jwt.sign(
        { id: results[0].user_id },
        process.env.JWT_SECRET,
        { expiresIn: "1h" }
      );
      res.json({ token });
    }
  );
});
// Forgot password
app.post("/api/auth/forgot-password", (req, res) => {
  const { email } = req.body;
  if (!email) return res.status(400).json({ message: "Email is required" });

  const genericResponse = {
    message: "If that email exists, a reset link has been sent.",
  };

  db.query(
    "SELECT user_id, email FROM user WHERE email = ?",
    [email],
    (err, rows) => {
      if (err) {
        console.error("Forgot password lookup error:", err);
        return res.status(200).json(genericResponse); // generic to avoid email enumeration
      }

      if (!rows.length) {
        return res.status(200).json(genericResponse);
      }

      const userId = rows[0].user_id;
      const token = crypto.randomBytes(32).toString("hex");
      const expires = new Date(Date.now() + 1000 * 60 * 60); // 1 hour

      db.query(
        "UPDATE user SET reset_token = ?, reset_expires = ? WHERE user_id = ?",
        [token, expires, userId],
        async (uerr) => {
          if (uerr) {
            console.error("Store reset token error:", uerr);
            return res.status(200).json(genericResponse);
          }

          const base = process.env.APP_URL || "http://localhost:3000";
          const resetUrl = `${base}/reset-password?token=${token}`;

          try {
            await sendResetEmail(email, resetUrl);
          } catch (mailErr) {
            console.error("Email send error:", mailErr.message);
          }

          if (process.env.NODE_ENV !== "production") {
            return res.json({ ...genericResponse, resetUrl }); // handy in dev
          }
          return res.json(genericResponse);
        }
      );
    }
  );
});

// Reset password
app.post("/api/auth/reset-password", async (req, res) => {
  const { token, password } = req.body;
  if (!token || !password) {
    return res
      .status(400)
      .json({ message: "Token and new password are required" });
  }

  db.query(
    "SELECT user_id FROM user WHERE reset_token = ? AND reset_expires > NOW()",
    [token],
    async (err, rows) => {
      if (err) {
        console.error("Reset lookup error:", err);
        return res.status(500).json({ message: "Server error" });
      }
      if (!rows.length) {
        return res.status(400).json({ message: "Invalid or expired token" });
      }

      const userId = rows[0].user_id;
      try {
        const hashed = await bcrypt.hash(password, 10);
        db.query(
          "UPDATE user SET password = ?, reset_token = NULL, reset_expires = NULL WHERE user_id = ?",
          [hashed, userId],
          (uerr) => {
            if (uerr) {
              console.error("Reset update error:", uerr);
              return res.status(500).json({ message: "Server error" });
            }
            return res.json({ message: "Password has been reset." });
          }
        );
      } catch (hashErr) {
        console.error("Bcrypt error:", hashErr);
        return res.status(500).json({ message: "Server error" });
      }
    }
  );
});

// Get current user (id from JWT)
app.get("/api/user", authenticate, (req, res) => {
  db.query(
    `SELECT 
       user_id       AS id,
       f_name,
       l_name,
       email,
       dob,
       gender,
       user_role
     FROM user
     WHERE user_id = ?`,
    [req.user.id],
    (err, results) => {
      if (err || !results.length) {
        console.error("User fetch error:", err);
        return res
          .status(500)
          .json({ message: "Error fetching user", error: err?.message });
      }
      res.json(results[0]);
    }
  );
});

// Habits Routes
app.post("/api/habits", authenticate, (req, res) => {
  const {
    description,
    frequency,
    time_preference,
    location,
    start_date,
    reminder_time,
  } = req.body;
  if (
    !description ||
    !frequency ||
    !time_preference ||
    !start_date ||
    !reminder_time
  ) {
    return res.status(400).json({ message: "Missing required fields" });
  }
  db.query(
    "INSERT INTO habits (description, frequency, time_preference, location, start_date, reminder_time, user_id, created_date) VALUES (?, ?, ?, ?, ?, ?, ?, NOW())",
    [
      description,
      frequency,
      time_preference,
      location || null,
      start_date,
      reminder_time,
      req.user.id,
    ],
    (err, results) => {
      if (err) {
        console.error("Habit creation error:", err);
        return res
          .status(500)
          .json({ message: "Error creating habit", error: err.message });
      }
      res
        .status(201)
        .json({ message: "Habit created", habit_id: results.insertId });
    }
  );
});

app.get("/api/habits", authenticate, (req, res) => {
  db.query(
    "SELECT * FROM habits WHERE user_id = ?",
    [req.user.id],
    (err, results) => {
      if (err) {
        console.error("Habit fetch error:", err);
        return res.status(500).json({ message: "Error fetching habits" });
      }
      res.json(results);
    }
  );
});

// Recommendation Endpoint
app.post("/api/recommend", authenticate, (req, res) => {
  const { habit_id, ...userData } = req.body;

  const python = spawn("python", [
    "predict_technique.py",
    JSON.stringify({ user_id: req.user.id, ...userData }),
  ]);

  let stdout = "",
    stderr = "";
  python.stdout.on("data", (d) => (stdout += d.toString()));
  python.stderr.on("data", (d) => (stderr += d.toString()));

  python.on("close", (code) => {
    if (code !== 0) {
      console.error("Python error:", stderr || stdout);
      return res
        .status(500)
        .json({ message: "Error generating recommendation" });
    }

    // parse JSON from Python
    let technique,
      rule_id = null,
      reason = null;
    try {
      const obj = JSON.parse(stdout.trim());
      technique = obj.technique;
      rule_id = obj.rule_id ?? null;
      reason = obj.reason ?? null;
    } catch {
      technique = stdout.trim(); // fallback if old script prints a plain string
    }
    if (!technique)
      return res.status(500).json({ message: "No technique returned" });

    const message = `Recommended technique: ${technique}`;

    db.query(
      `INSERT INTO recommendations
         (message, user_id, habit_id, reason, rule_id, generated_on)
       VALUES (?, ?, ?, ?, ?, NOW())`,
      [message, req.user.id, habit_id || null, reason, rule_id],
      (err, results) => {
        if (err) {
          console.error("DB error:", err);
          return res
            .status(500)
            .json({ message: "Error saving recommendation" });
        }
        res.json({
          rec_id: results.insertId,
          recommended_technique: technique,
          reason,
          rule_id,
        });
      }
    );
  });
});
// ===== HABIT LOGS =====

// Create / update a log (one per day)
app.post("/api/habit-logs", authenticate, (req, res) => {
  const { habit_id, log_date, status, notes, feedback_rating } = req.body;
  if (!habit_id || !log_date || !status) {
    return res
      .status(400)
      .json({ message: "habit_id, log_date and status are required" });
  }

  // 1) verify habit belongs to the logged-in user
  db.query(
    "SELECT user_id FROM habits WHERE habit_id = ?",
    [habit_id],
    (err, rows) => {
      if (err) {
        console.error("Check habit ownership error:", err);
        return res.status(500).json({ message: "Server error" });
      }
      if (!rows.length || rows[0].user_id !== req.user.id) {
        return res.status(403).json({ message: "Not your habit" });
      }

      // 2) upsert log
      const sql = `
        INSERT INTO habit_logs (habit_id, log_date, status, notes, feedback_rating)
        VALUES (?, ?, ?, ?, ?)
        ON DUPLICATE KEY UPDATE
          status = VALUES(status),
          notes = VALUES(notes),
          feedback_rating = VALUES(feedback_rating)
      `;
      const params = [
        habit_id,
        log_date, // "YYYY-MM-DD"
        status, // 'completed' | 'missed' | 'skipped' (match your ENUM)
        notes || null,
        feedback_rating ?? null,
      ];
      db.query(sql, params, (err2) => {
        if (err2) {
          console.error("Upsert habit log error:", err2);
          return res.status(500).json({ message: "Error saving log" });
        }
        res.status(200).json({ message: "Log saved" });
      });
    }
  );
});

// Fetch logs in a date range for a habit (for calendar etc.)
app.get("/api/habit-logs", authenticate, (req, res) => {
  const { habit_id, start, end } = req.query;
  if (!habit_id) {
    return res.status(400).json({ message: "habit_id is required" });
  }

  // verify ownership
  db.query(
    "SELECT user_id FROM habits WHERE habit_id = ?",
    [habit_id],
    (err, rows) => {
      if (err) return res.status(500).json({ message: "Server error" });
      if (!rows.length || rows[0].user_id !== req.user.id) {
        return res.status(403).json({ message: "Not your habit" });
      }

      let sql =
        "SELECT log_id, habit_id, log_date, status, notes, feedback_rating FROM habit_logs WHERE habit_id = ?";
      const params = [habit_id];

      if (start && end) {
        sql += " AND log_date BETWEEN ? AND ?";
        params.push(start, end);
      }

      db.query(sql, params, (err2, rows2) => {
        if (err2) return res.status(500).json({ message: "Server error" });
        res.json(rows2);
      });
    }
  );
});

// Patterns Endpoint
app.get("/api/patterns", authenticate, (req, res) => {
  const pythonProcess = spawn("python", [
    "pattern_recognition.py",
    req.user.id.toString(),
  ]);

  let output = "";
  pythonProcess.stdout.on("data", (data) => {
    output += data.toString();
  });

  pythonProcess.on("close", (code) => {
    if (code !== 0)
      return res.status(500).json({ message: "Error analyzing patterns" });
    try {
      res.json({ patterns: JSON.parse(output) });
    } catch (e) {
      res.status(500).json({ message: "Invalid JSON from patterns script" });
    }
  });

  pythonProcess.stderr.on("data", (data) => {
    console.error(`Python error: ${data}`);
  });
});

// Feedback Endpoint
app.post("/api/feedback", authenticate, (req, res) => {
  const { rec_id, feedback_rating, feedback_comment } = req.body;
  if (!rec_id || !feedback_rating) {
    return res.status(400).json({ message: "Missing required fields" });
  }
  db.query(
    "INSERT INTO recommendation_feedback (rec_id, feedback_rating, feedback_comment) VALUES (?, ?, ?)",
    [rec_id, feedback_rating, feedback_comment || null],
    (err) => {
      if (err) {
        console.error("Feedback save error:", err);
        return res
          .status(500)
          .json({ message: "Error saving feedback", error: err.message });
      }
      res.status(201).json({ message: "Feedback saved" });
    }
  );
});

// Recommendations Endpoint
app.get("/api/recommendations", authenticate, (req, res) => {
  db.query(
    "SELECT * FROM recommendations WHERE user_id = ?",
    [req.user.id],
    (err, results) => {
      if (err) {
        console.error("Recommendations fetch error:", err);
        return res.status(500).json({
          message: "Error fetching recommendations",
          error: err.message,
        });
      }
      res.json(results);
    }
  );
});

// Feedback Loop Endpoint
app.post("/api/run-feedback-loop", authenticate, (req, res) => {
  const pythonProcess = spawn("python", ["feedback_loop.py"]);
  pythonProcess.on("close", (code) => {
    res.json({ status: code === 0 ? "Success" : "Failure" });
  });
  pythonProcess.stderr.on("data", (data) => {
    console.error(`Feedback loop error: ${data}`);
  });
});

// Cron Schedule for Feedback Loop
cron.schedule("0 0 * * *", () => {
  console.log("Running scheduled feedback loop...");
  const pythonProcess = spawn("python", ["feedback_loop.py"]);
  pythonProcess.stdout.on("data", (data) => {
    console.log(`Feedback loop output: ${data}`);
  });
  pythonProcess.on("close", (code) => {
    if (code === 0) {
      console.log("Feedback loop completed successfully.");
    } else {
      console.error(`Feedback loop exited with code ${code}`);
    }
  });
  pythonProcess.stderr.on("data", (data) => {
    console.error(`Feedback loop error: ${data}`);
  });
});

app.listen(process.env.PORT || 5000, () =>
  console.log("Server running on port 5000")
);
