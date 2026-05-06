import React from "react";

function formatPrice(listing) {
  const n = listing.price?.toLocaleString("en-US") || "";
  if (!n) return "";
  return listing.listing_type === "rent" ? `$${n}/mo` : `$${n}`;
}

function humaniseTag(tag) {
  return tag.replace(/_/g, " ");
}

function InlineListingCard({ listing }) {
  const img = listing.images?.[0];
  const tags = (listing.tags || []).slice(0, 3);
  return (
    <div className="inline-card">
      {img ? (
        <img
          className="inline-card-img"
          src={img}
          alt={listing.title}
          onError={(e) => {
            e.currentTarget.style.display = "none";
          }}
        />
      ) : (
        <div className="inline-card-img inline-card-img-placeholder">
          No photo
        </div>
      )}
      <div className="inline-card-body">
        <div className="inline-card-price">{formatPrice(listing)}</div>
        <div className="inline-card-title">{listing.title}</div>
        <div className="inline-card-meta">
          {listing.bedrooms != null && <span>{listing.bedrooms} bd</span>}
          {listing.bathrooms != null && <span>{listing.bathrooms} ba</span>}
          {listing.area_sqft != null && <span>{listing.area_sqft} sqft</span>}
          {listing.property_type && <span>{listing.property_type}</span>}
        </div>
        <div className="inline-card-location">
          {listing.neighbourhood ? `${listing.neighbourhood}, ` : ""}
          {listing.city}
        </div>
        {tags.length > 0 && (
          <div className="inline-card-tags">
            {tags.map((t) => (
              <span key={t} className="inline-card-tag">
                {humaniseTag(t)}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function MessageBubble({ message }) {
  const { role, content, typing, listings } = message;
  const cls = `bubble ${role}${typing ? " typing" : ""}`;
  const hasListings = Array.isArray(listings) && listings.length > 0;
  return (
    <div className={cls}>
      <div>{content}</div>
      {hasListings && (
        <div className="bubble-listings">
          {listings.map((l) => (
            <InlineListingCard key={l.id} listing={l} />
          ))}
        </div>
      )}
    </div>
  );
}
