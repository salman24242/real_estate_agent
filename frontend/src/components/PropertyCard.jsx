import React from "react";

function formatPrice(listing) {
  const n = listing.price?.toLocaleString("en-US") || "";
  if (!n) return "";
  return listing.listing_type === "rent" ? `$${n}/mo` : `$${n}`;
}

function humaniseTag(tag) {
  return tag.replace(/_/g, " ");
}

export default function PropertyCard({ listing, onSelect }) {
  const img = listing.images?.[0];
  const tagsToShow = (listing.tags || []).slice(0, 4);
  const hiddenCount = Math.max(0, (listing.tags || []).length - tagsToShow.length);

  return (
    <div className="card" onClick={() => onSelect?.(listing)}>
      {img ? (
        <img
          className="image"
          src={img}
          alt={listing.title}
          onError={(e) => {
            e.currentTarget.style.display = "none";
          }}
        />
      ) : (
        <div className="image-placeholder">No photo</div>
      )}
      <div className="body">
        <div className="price">{formatPrice(listing)}</div>
        <div className="title">{listing.title}</div>
        <div className="meta">
          {listing.bedrooms != null && <span>{listing.bedrooms} bd</span>}
          {listing.bathrooms != null && <span>{listing.bathrooms} ba</span>}
          {listing.area_sqft != null && <span>{listing.area_sqft} sqft</span>}
          {listing.property_type && <span>{listing.property_type}</span>}
        </div>
        <div className="location">
          {listing.neighbourhood ? `${listing.neighbourhood}, ` : ""}
          {listing.city}
        </div>
        {tagsToShow.length > 0 && (
          <div className="tags">
            {tagsToShow.map((t) => (
              <span key={t} className="tag">{humaniseTag(t)}</span>
            ))}
            {hiddenCount > 0 && (
              <span className="tag more">+{hiddenCount} more</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
