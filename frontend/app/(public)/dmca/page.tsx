"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { publicFetch } from "@/lib/public-api";

export default function DmcaPage() {
  const [complainantName, setComplainantName] = useState("");
  const [complainantEmail, setComplainantEmail] = useState("");
  const [complainantPhone, setComplainantPhone] = useState("");
  const [infringingUrl, setInfringingUrl] = useState("");
  const [description, setDescription] = useState("");
  const [originalWorkUrl, setOriginalWorkUrl] = useState("");
  const [originalWorkDescription, setOriginalWorkDescription] = useState("");
  const [signatureName, setSignatureName] = useState("");
  const [signatureCheck, setSignatureCheck] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  function reset() {
    setComplainantName("");
    setComplainantEmail("");
    setComplainantPhone("");
    setInfringingUrl("");
    setDescription("");
    setOriginalWorkUrl("");
    setOriginalWorkDescription("");
    setSignatureName("");
    setSignatureCheck(false);
    setError(null);
    setSuccess(false);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(false);
    try {
      await publicFetch("/api/public/dmca", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          complainant_name: complainantName,
          complainant_email: complainantEmail,
          complainant_phone: complainantPhone || undefined,
          infringing_url: infringingUrl,
          description,
          original_work_url: originalWorkUrl || undefined,
          original_work_description: originalWorkDescription || undefined,
          signature: signatureName,
        }),
      });
      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit notice.");
    } finally {
      setLoading(false);
    }
  }

  const inputClass =
    "flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm outline-none ring-offset-background placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50";

  return (
    <main className="mx-auto max-w-3xl px-4 py-20 sm:px-6 lg:px-8 lg:py-24">
      <header>
        <p className="font-metadata text-xs uppercase tracking-[0.24em] text-accent">
          Dokushodo
        </p>
        <h1 className="mt-4 font-literary text-4xl font-medium leading-tight tracking-normal text-foreground md:text-5xl">
          DMCA
        </h1>
      </header>

      <section className="mt-8 space-y-4 text-sm leading-7 text-muted-foreground">
        <p>
          Dokushodo respects intellectual property rights and expects its users
          to do the same. In accordance with the Digital Millennium Copyright Act
          (DMCA), we will respond promptly to notices of alleged copyright
          infringement submitted to the designated copyright agent.
        </p>
        <p>
          If you believe material available through Dokushodo infringes your
          copyright, submit a written notice containing the following
          information. Inaccurate or misleading information may result in
          liability for damages, so consult legal counsel before submitting a
          notice if you are unsure whether your copyright is being infringed.
        </p>
        <ul className="list-disc space-y-1 pl-6">
          <li>
            Your physical or electronic signature (type your full legal name
            below).
          </li>
          <li>
            Identification of the copyrighted work you claim has been infringed.
          </li>
          <li>
            Identification of the material that is infringing and its location
            (the URL).
          </li>
          <li>
            Your name, email address, and phone number so we can contact you.
          </li>
          <li>
            A statement that you have a good-faith belief the use is not
            authorized by the copyright owner, its agent, or the law.
          </li>
          <li>
            A statement, under penalty of perjury, that the information in the
            notice is accurate and that you are the copyright owner or authorized
            to act on the owner&apos;s behalf.
          </li>
        </ul>
        <p>
          Upon receipt of a valid notice, Dokushodo will remove or disable
          access to the allegedly infringing material and notify the affected
          user. Counter-notices may be submitted by the user in accordance with
          the DMCA.
        </p>
      </section>

      {success ? (
        <div className="mt-12 rounded-md border border-border bg-background p-6">
          <p className="font-literary text-lg font-medium text-foreground">
            Notice submitted
          </p>
          <p className="mt-2 text-sm leading-7 text-muted-foreground">
            Your DMCA takedown notice has been received. The owner will review
            it and take appropriate action. You will be contacted at the email
            address you provided if more information is needed.
          </p>
          <Button className="mt-6" onClick={reset}>
            Submit another
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
            <label
              htmlFor="complainant_name"
              className="text-sm font-medium text-foreground"
            >
              Full name
            </label>
            <Input
              id="complainant_name"
              value={complainantName}
              onChange={(e) => setComplainantName(e.target.value)}
              required
              placeholder="Your legal name"
              disabled={loading}
            />
          </div>

          <div className="space-y-2">
            <label
              htmlFor="complainant_email"
              className="text-sm font-medium text-foreground"
            >
              Email
            </label>
            <Input
              id="complainant_email"
              type="email"
              value={complainantEmail}
              onChange={(e) => setComplainantEmail(e.target.value)}
              required
              placeholder="you@example.com"
              disabled={loading}
            />
          </div>

          <div className="space-y-2">
            <label
              htmlFor="complainant_phone"
              className="text-sm font-medium text-foreground"
            >
              Phone <span className="text-muted-foreground">(optional)</span>
            </label>
            <Input
              id="complainant_phone"
              type="tel"
              value={complainantPhone}
              onChange={(e) => setComplainantPhone(e.target.value)}
              placeholder="+1-555-123-4567"
              disabled={loading}
            />
          </div>

          <div className="space-y-2">
            <label
              htmlFor="infringing_url"
              className="text-sm font-medium text-foreground"
            >
              Infringing material URL
            </label>
            <Input
              id="infringing_url"
              type="url"
              value={infringingUrl}
              onChange={(e) => setInfringingUrl(e.target.value)}
              required
              placeholder="https://dokushodo.app/novels/..."
              disabled={loading}
            />
          </div>

          <div className="space-y-2">
            <label
              htmlFor="description"
              className="text-sm font-medium text-foreground"
            >
              Description of infringement
            </label>
            <Textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              required
              placeholder="Describe how the material infringes your copyright."
              disabled={loading}
            />
          </div>

          <div className="space-y-2">
            <label
              htmlFor="original_work_url"
              className="text-sm font-medium text-foreground"
            >
              Original work URL <span className="text-muted-foreground">(optional)</span>
            </label>
            <Input
              id="original_work_url"
              type="url"
              value={originalWorkUrl}
              onChange={(e) => setOriginalWorkUrl(e.target.value)}
              placeholder="https://..."
              disabled={loading}
            />
          </div>

          <div className="space-y-2">
            <label
              htmlFor="original_work_description"
              className="text-sm font-medium text-foreground"
            >
              Original work description{" "}
              <span className="text-muted-foreground">(optional)</span>
            </label>
            <Textarea
              id="original_work_description"
              value={originalWorkDescription}
              onChange={(e) => setOriginalWorkDescription(e.target.value)}
              placeholder="Describe the original copyrighted work."
              disabled={loading}
            />
          </div>

          <hr className="border-border" />

          <div className="space-y-3">
            <div className="flex items-start gap-3">
              <input
                id="signature_check"
                type="checkbox"
                checked={signatureCheck}
                onChange={(e) => setSignatureCheck(e.target.checked)}
                disabled={loading}
                className="mt-1 h-4 w-4 rounded border-input accent-accent"
              />
              <label htmlFor="signature_check" className="text-sm leading-6 text-muted-foreground">
                I have a good-faith belief that the use of the material described
                above is not authorized by the copyright owner, its agent, or the
                law. The information in this notice is accurate, and I am the
                copyright owner or authorized to act on the owner&apos;s behalf.
                I understand that submitting a false claim may result in legal
                liability.
              </label>
            </div>

            <div className="space-y-2">
              <label
                htmlFor="signature_name"
                className="text-sm font-medium text-foreground"
              >
                Electronic signature <span className="text-muted-foreground">(type your full legal name)</span>
              </label>
              <Input
                id="signature_name"
                value={signatureName}
                onChange={(e) => setSignatureName(e.target.value)}
                required
                placeholder="Type your full legal name as your electronic signature"
                disabled={loading}
              />
            </div>
          </div>

          <Button
            type="submit"
            disabled={loading || !signatureCheck || !signatureName.trim()}
            className="w-full sm:w-auto"
          >
            {loading ? "Submitting..." : "Submit DMCA notice"}
          </Button>
        </form>
      )}
    </main>
  );
}
