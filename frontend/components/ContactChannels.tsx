import React from "react";
import { Mail, Phone, Globe, MessageSquare } from "lucide-react";

interface ContactChannelsProps {
  websiteUrl?: string | null;
  phone?: string | null;
  emails?: string[];
  phones?: string[];
}

export function ContactChannels({
  websiteUrl,
  phone,
  emails = [],
  phones = [],
}: ContactChannelsProps) {
  const hasEmail = emails.length > 0;
  const directPhone = phone || (phones.length > 0 ? phones[0] : null);
  const hasPhone = Boolean(directPhone);

  return (
    <div className="flex items-center gap-1.5" title="Available Contact Channels">
      {hasEmail ? (
        <span
          className="p-1 rounded bg-blue-50 text-blue-600 border border-blue-100"
          title={`Email available: ${emails[0]}`}
        >
          <Mail className="h-3.5 w-3.5" />
        </span>
      ) : (
        <span className="p-1 rounded text-slate-300" title="No public email found">
          <Mail className="h-3.5 w-3.5" />
        </span>
      )}

      {hasPhone ? (
        <span
          className="p-1 rounded bg-emerald-50 text-emerald-600 border border-emerald-100"
          title={`Phone available: ${directPhone}`}
        >
          <Phone className="h-3.5 w-3.5" />
        </span>
      ) : (
        <span className="p-1 rounded text-slate-300" title="No phone found">
          <Phone className="h-3.5 w-3.5" />
        </span>
      )}

      {hasPhone && (
        <span
          className="p-1 rounded bg-green-50 text-green-700 border border-green-200"
          title="WhatsApp channel ready"
        >
          <MessageSquare className="h-3.5 w-3.5" />
        </span>
      )}

      {websiteUrl ? (
        <a
          href={websiteUrl}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="p-1 rounded bg-slate-100 text-slate-600 hover:text-blue-600 border border-slate-200 transition"
          title={`Visit website: ${websiteUrl}`}
        >
          <Globe className="h-3.5 w-3.5" />
        </a>
      ) : (
        <span className="p-1 rounded text-slate-300" title="No website">
          <Globe className="h-3.5 w-3.5" />
        </span>
      )}
    </div>
  );
}
