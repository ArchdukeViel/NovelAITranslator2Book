"use client";

import { useState, type FormEvent } from "react";

import { PageHeading } from "@/components/admin/page-heading";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { useUiStore } from "@/lib/store";

function maskToken(token: string) {
  const trimmed = token.trim();
  if (trimmed.length <= 8) {
    return `${trimmed.slice(0, 2)}****`;
  }
  return `${trimmed.slice(0, 4)}****${trimmed.slice(-4)}`;
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }
  return date.toLocaleDateString();
}

export default function SettingsPage() {
  const [draftToken, setDraftToken] = useState("");
  const { addApiToken, apiTokens, applyDummyApiToken, removeApiToken } = useUiStore();

  function handleAddToken(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    addApiToken(draftToken);
    setDraftToken("");
  }

  return (
    <>
      <PageHeading title="Settings" description="Manage API token access for the admin workspace." />

      <div className="space-y-5">
        <Panel>
          <PanelHeader>
            <PanelTitle>API Token</PanelTitle>
          </PanelHeader>
          <PanelBody>
            <form className="space-y-4" onSubmit={handleAddToken}>
              <div className="space-y-2">
                <label className="block text-sm font-medium" htmlFor="api-token">
                  Add API Token
                </label>
                <Input
                  id="api-token"
                  type="password"
                  value={draftToken}
                  onChange={(event) => setDraftToken(event.target.value)}
                  placeholder="Enter your API token here..."
                />
                <p className="text-sm text-muted-foreground">
                  Stored in this browser and used for admin API requests.
                </p>
              </div>

              <div className="flex flex-col gap-2 sm:flex-row">
                <Button className="flex-1" type="submit">
                  Add API Key
                </Button>
                <Button className="sm:w-48" type="button" variant="secondary" onClick={applyDummyApiToken}>
                  Apply Dummy API
                </Button>
              </div>
            </form>
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader>
            <PanelTitle>Your API Tokens</PanelTitle>
          </PanelHeader>
          <PanelBody className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b bg-muted/40">
                  <tr>
                    <th className="px-4 py-3 font-medium">Type</th>
                    <th className="px-4 py-3 font-medium">Token</th>
                    <th className="px-4 py-3 font-medium">Added On</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {apiTokens.length ? (
                    apiTokens.map((entry) => (
                      <tr className="border-b last:border-0" key={entry.id}>
                        <td className="px-4 py-3">{entry.type}</td>
                        <td className="px-4 py-3 font-mono text-xs">{maskToken(entry.token)}</td>
                        <td className="px-4 py-3">{formatDate(entry.addedOn)}</td>
                        <td className="px-4 py-3">
                          <Badge tone={entry.status === "Active" ? "green" : "neutral"}>{entry.status}</Badge>
                        </td>
                        <td className="px-4 py-3">
                          <Button
                            type="button"
                            variant="destructive"
                            size="sm"
                            onClick={() => removeApiToken(entry.id)}
                          >
                            Remove
                          </Button>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td className="px-4 py-6 text-center text-muted-foreground" colSpan={5}>
                        No API tokens added.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </PanelBody>
        </Panel>
      </div>
    </>
  );
}
