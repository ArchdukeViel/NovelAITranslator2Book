"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { publicFetch } from "@/lib/public-api";

export default function ContactPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(false);
    try {
      await publicFetch("/api/public/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, subject, message }),
      });
      setSuccess(true);
      setName("");
      setEmail("");
      setSubject("");
      setMessage("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send message.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-20 sm:px-6 lg:px-8 lg:py-24">
      <header>
        <p className="font-metadata text-xs uppercase tracking-[0.24em] text-accent">
          Dokushodo
        </p>
        <h1 className="mt-4 font-literary text-4xl font-medium leading-tight tracking-normal text-foreground md:text-5xl">
          Contact
        </h1>
        <p className="mt-6 text-base leading-8 text-muted-foreground">
          Send a message to the Dokushodo owner or admin. All fields are
          required unless marked optional.
        </p>
      </header>

      {success ? (
        <div className="mt-12 rounded-md border border-border bg-background p-6">
          <p className="font-literary text-lg font-medium text-foreground">
            Message sent
          </p>
          <p className="mt-2 text-sm leading-7 text-muted-foreground">
            Thank you. Your message has been submitted. The owner will review it
            and respond if needed.
          </p>
          <Button className="mt-6" onClick={() => setSuccess(false)}>
            Send another
          </Button>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="mt-12 space-y-6">
          {error && (
            <div className="rounded-md border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
              {error}
            </div>
          )}

          <div className="space-y-2">
            <label htmlFor="name" className="text-sm font-medium text-foreground">
              Name
            </label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              placeholder="Your name"
              disabled={loading}
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="email" className="text-sm font-medium text-foreground">
              Email
            </label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="you@example.com"
              disabled={loading}
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="subject" className="text-sm font-medium text-foreground">
              Subject
            </label>
            <Input
              id="subject"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              required
              placeholder="What is this about?"
              disabled={loading}
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="message" className="text-sm font-medium text-foreground">
              Message
            </label>
            <Textarea
              id="message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              required
              placeholder="Describe your issue, question, or request in detail."
              disabled={loading}
            />
          </div>

          <Button type="submit" disabled={loading} className="w-full sm:w-auto">
            {loading ? "Sending..." : "Send"}
          </Button>
        </form>
      )}
    </main>
  );
}
