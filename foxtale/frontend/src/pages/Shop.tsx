import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ExternalLink, Heart, Search, ShoppingBag, ShieldCheck, Sparkles } from "lucide-react";
import { ProductCard } from "../components/Skincare";
import { PageHeader, SectionTitle } from "../components/ui";
import { useApp } from "../context/AppContext";
import { cartUrl, comboImageUrl, getCatalog, getReport, listScans } from "../services/api";
import type { Catalog, CatalogProduct, Combo } from "../services/api";
import type { Suggestion } from "../types/analysis";
import { rupees } from "../lib/format";
import { Reveal, Skeleton } from "../lib/motion";

const TABS = [
  ["all", "All"], ["cleanse", "Cleanse"], ["treat", "Treat"], ["eye", "Eye care"], ["moisturize", "Moisturize"], ["protect", "Protect"],
  ["combos", "Combos"], ["wishlist", "Wishlist"],
] as const;

const CONCERN_LABEL: Record<string, string> = {
  acne: "Acne", texture: "Texture", tone_evenness: "Even tone", anti_aging: "Fine lines", hydration: "Hydration", oil_control: "Oil control",
  redness: "Redness", dark_spots: "Dark spots", brightening: "Brightening", pores: "Pores",
};

// user concern keys (from the scan report) -> combo concern keys
const CONCERN_MAP: Record<string, string[]> = {
  acne_like_spots: ["acne"], blackheads: ["acne"], texture: ["texture"], tone_evenness: ["tone_evenness", "brightening"],
  fine_lines: ["anti_aging"], dryness_indicators: ["hydration"], oiliness: ["oil_control"], pores: ["oil_control", "pores"],
  redness: ["redness"], dark_spots: ["dark_spots", "brightening"], acne_scars: ["dark_spots"],
};

const PREGNANCY_HIDDEN = new Set(["retinol-serum", "aha-bha-serum", "exfoliating-toner"]);

function ComboCard({ c, matched, index }: { c: Combo; matched: string[]; index: number }) {
  return (
    <Reveal index={index} className="h-full">
      <article className="lift flex h-full flex-col rounded-2xl border border-line bg-card p-3 shadow-card hover:border-fox-300">
        <div className="zoom-img relative aspect-square overflow-hidden rounded-xl">
          <img src={comboImageUrl(c.image)} alt={c.name} loading="lazy" className="h-full w-full object-cover" />
          {matched.length > 0 && <span className="pill absolute left-2 top-2 bg-fox-600 text-white shadow-glow">Good match for you</span>}
        </div>
        <h3 className="mt-3 text-[14px] font-extrabold leading-snug text-ink">{c.name}</h3>
        <p className="mt-1 text-xl font-extrabold text-ink">{rupees(c.price_inr)} <span className="text-[11px] font-normal text-muted">on foxtale.in</span></p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {c.concerns.map((k) => <span key={k} className={`pill ${matched.includes(k) ? "bg-fox-50 text-fox-text dark:bg-fox-500/15 dark:text-fox-300" : "bg-soft text-muted"}`}>{CONCERN_LABEL[k] ?? k}</span>)}
          {c.highlights.map((h) => <span key={h} className="pill bg-soft text-muted">{h}</span>)}
        </div>
        <div className="mt-auto flex items-center gap-2 pt-4">
          <a href={cartUrl([c.variant_id])} target="_blank" rel="noreferrer" className="btn-cta flex-1 !py-2 text-[13px]" aria-label={`Buy ${c.name} on foxtale.in`}><ShoppingBag size={15} /> Buy combo</a>
          <a href={c.url} target="_blank" rel="noreferrer" className="rounded-full p-2 text-fox-500 hover:bg-fox-50 dark:hover:bg-fox-500/10" aria-label={`See what is inside ${c.name}`} title="See what is inside on foxtale.in"><ExternalLink size={16} /></a>
        </div>
      </article>
    </Reveal>
  );
}

export default function Shop() {
  const { settings, updateSettings, profile, toast } = useApp();
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [recommended, setRecommended] = useState<Record<string, string>>({}); // product id -> reason
  const [userConcerns, setUserConcerns] = useState<string[]>([]);
  const [tab, setTab] = useState<(typeof TABS)[number][0]>("all");
  const [query, setQuery] = useState("");
  const [concern, setConcern] = useState("all");
  const [skin, setSkin] = useState("all");
  const [sort, setSort] = useState<"recommended" | "low" | "high">("recommended");
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    getCatalog().then(setCatalog).catch(() => setCatalog({ products: [], combos: [], comboNote: "", catalogDate: "", priceNote: "" }));
    listScans()
      .then(async (all) => {
        if (!all.length) return;
        const r = await getReport({ analysis: all[0].analysis, regions: all[0].regions });
        setRecommended(Object.fromEntries(r.skincare.suggestions.map((s) => [s.id, s.reason])));
        setUserConcerns(r.skincare.concerns.map((c) => c.key));
      })
      .catch(() => undefined);
  }, []);

  const owned = settings.owned_products;
  const wishlist = settings.wishlist ?? [];
  const goals = profile?.goals ?? [];
  const wantedConcerns = useMemo(() => new Set([...userConcerns.flatMap((k) => CONCERN_MAP[k] ?? []), ...goals]), [userConcerns, goals]);

  // things the profile rules out (pregnancy, sensitivity, allergies)
  const blocked = useCallback((p: CatalogProduct): string | null => {
    if (profile?.pregnant && PREGNANCY_HIDDEN.has(p.id)) return "pregnancy";
    if (profile?.sensitive_skin && p.active) return "sensitive skin";
    const tokens = (profile?.allergies ?? "").toLowerCase().split(/[,;/\n]+/).map((t) => t.trim()).filter((t) => t.length >= 3);
    const text = (p.name + " " + p.ingredients.join(" ")).toLowerCase();
    return tokens.some((t) => text.includes(t)) ? "an allergy you listed" : null;
  }, [profile]);

  const products = useMemo(() => {
    if (!catalog) return [];
    let list = catalog.products;
    if (tab === "wishlist") list = list.filter((p) => wishlist.includes(p.id));
    else if (!["all", "combos"].includes(tab)) list = list.filter((p) => p.step === tab);
    const q = query.trim().toLowerCase();
    if (q) list = list.filter((p) => (p.name + " " + p.ingredients.join(" ") + " " + p.targetLabels.join(" ")).toLowerCase().includes(q));
    if (concern !== "all") list = list.filter((p) => p.targetLabels.includes(concern));
    if (skin !== "all") list = list.filter((p) => p.skinTypes.includes(skin));
    const score = (p: CatalogProduct) => (recommended[p.id] ? 5 : 0) + p.targets.filter((t) => wantedConcerns.has(t) || (CONCERN_MAP[t] ?? []).some((k) => wantedConcerns.has(k))).length;
    const sorted = [...list];
    if (sort === "low") sorted.sort((a, b) => (a.price ?? 1e9) - (b.price ?? 1e9));
    else if (sort === "high") sorted.sort((a, b) => (b.price ?? -1) - (a.price ?? -1));
    else sorted.sort((a, b) => score(b) - score(a));
    return sorted;
  }, [catalog, tab, query, concern, skin, sort, recommended, wishlist, wantedConcerns]);

  const hidden = products.filter((p) => blocked(p));
  const visible = showAll ? products : products.filter((p) => !blocked(p));

  const combos = useMemo(() => {
    if (!catalog) return [];
    const q = query.trim().toLowerCase();
    return catalog.combos
      .filter((c) => !(profile?.pregnant && (c.has_retinol || c.has_acids)) && !(profile?.sensitive_skin && (c.has_retinol || c.has_acids)))
      .filter((c) => !q || (c.name + c.highlights.join(" ")).toLowerCase().includes(q))
      .map((c) => ({ c, matched: c.concerns.filter((k) => wantedConcerns.has(k)) }))
      .sort((a, b) => b.matched.length - a.matched.length);
  }, [catalog, query, wantedConcerns, profile]);

  const concernOptions = useMemo(() => [...new Set((catalog?.products ?? []).flatMap((p) => p.targetLabels))].sort(), [catalog]);

  const setOwned = (id: string, isOwned: boolean) => updateSettings({ owned_products: isOwned ? [...owned.filter((x) => x !== id), id] : owned.filter((x) => x !== id) });
  const toggleWish = (id: string) => {
    updateSettings({ wishlist: wishlist.includes(id) ? wishlist.filter((x) => x !== id) : [...wishlist, id] });
    toast(wishlist.includes(id) ? "Removed from wishlist" : "Saved to your wishlist");
  };

  const asSuggestion = (p: CatalogProduct): Suggestion => ({
    id: p.id, name: p.name, step: p.step, stepLabel: p.stepLabel, when: p.when, ingredients: p.ingredients,
    reason: recommended[p.id] ?? "", howItWorks: p.howItWorks, howToUse: p.howToUse, caution: p.caution, url: p.url, size: p.size,
    price: p.price, priceSource: p.priceSource, shape: p.shape, variantId: p.variantId, owned: owned.includes(p.id), image: p.image,
  });

  return (
    <div>
      <PageHeader title="Shop Foxtale" subtitle="Every Foxtale product and combo in one place, ranked for your skin. Buying happens on foxtale.in." />

      <div className="card mb-5 p-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative min-w-[220px] flex-1">
            <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-muted" />
            <input className="input !pl-10" placeholder="Search products, ingredients or concerns..." value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search the shop" />
          </div>
          {tab !== "combos" && (
            <>
              <select className="input !w-auto !rounded-full" value={concern} onChange={(e) => setConcern(e.target.value)} aria-label="Concern">
                <option value="all">Any concern</option>
                {concernOptions.map((c) => <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>)}
              </select>
              <select className="input !w-auto !rounded-full" value={skin} onChange={(e) => setSkin(e.target.value)} aria-label="Skin type">
                <option value="all">Any skin type</option><option value="oily">Oily</option><option value="dry">Dry</option><option value="combination">Combination</option><option value="normal">Normal</option>
              </select>
              <select className="input !w-auto !rounded-full" value={sort} onChange={(e) => setSort(e.target.value as typeof sort)} aria-label="Sort">
                <option value="recommended">Best for me</option><option value="low">Price: low to high</option><option value="high">Price: high to low</option>
              </select>
            </>
          )}
        </div>
        <div className="mt-3 flex flex-wrap gap-2" role="tablist" aria-label="Category">
          {TABS.map(([k, label]) => (
            <button key={k} role="tab" aria-selected={tab === k} className={`chip !py-1.5 text-[13px] ${tab === k ? "chip-on" : ""}`} onClick={() => setTab(k)}>
              {k === "wishlist" && <Heart size={13} />} {label}{k === "wishlist" && wishlist.length ? ` (${wishlist.length})` : ""}
            </button>
          ))}
        </div>
      </div>

      {!catalog && <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-96" />)}</div>}

      {catalog && tab !== "combos" && (
        <>
          {hidden.length > 0 && !showAll && (
            <p className="mb-4 flex flex-wrap items-center gap-2 rounded-2xl bg-soft p-3 text-sm text-muted">
              <ShieldCheck size={16} className="text-emerald-600" /> {hidden.length} product{hidden.length === 1 ? " is" : "s are"} hidden because of your profile answers (pregnancy, sensitive skin or allergies).
              <button className="font-bold text-fox-text underline dark:text-fox-300" onClick={() => setShowAll(true)}>Show anyway</button>
            </p>
          )}
          {showAll && hidden.length > 0 && <p className="mb-4 text-sm text-muted">Showing everything. Products marked below may not suit your profile; read the label and ask a doctor if unsure. <button className="font-bold text-fox-text underline dark:text-fox-300" onClick={() => setShowAll(false)}>Hide them again</button></p>}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {visible.map((p, i) => (
              <Reveal key={p.id} index={i % 8} className="h-full">
                <div className="relative h-full">
                  {recommended[p.id] && <span className="pill absolute -top-2 left-3 z-10 bg-fox-600 text-white shadow-glow"><Sparkles size={11} className="mr-1" /> Picked for you</span>}
                  {blocked(p) && <span className="pill absolute -top-2 right-3 z-10 bg-amber-100 text-amber-800">Check: {blocked(p)}</span>}
                  <ProductCard s={asSuggestion(p)} index={i + 1} showIndex={false} onOwned={setOwned} wished={wishlist.includes(p.id)} onWish={toggleWish} />
                </div>
              </Reveal>
            ))}
          </div>
          {visible.length === 0 && (
            <p className="card p-8 text-center text-sm text-muted">
              {tab === "wishlist" ? "Nothing in your wishlist yet. Tap the heart on any product." : "No products match. Try clearing a filter."}
            </p>
          )}
        </>
      )}

      {catalog && (tab === "combos" || tab === "all") && combos.length > 0 && (
        <section className={tab === "all" ? "mt-10" : ""}>
          <SectionTitle title="Foxtale combos" subtitle="Ready-made sets from Foxtale, with the best matches for your skin first." icon={<ShoppingBag size={18} />} />
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {combos.slice(0, tab === "all" ? 4 : undefined).map(({ c, matched }, i) => <ComboCard key={c.id} c={c} matched={matched} index={i} />)}
          </div>
          {tab === "all" && combos.length > 4 && <button className="btn-soft mt-4" onClick={() => setTab("combos")}>See all {combos.length} combos</button>}
          <p className="mt-4 text-[11.5px] leading-relaxed text-muted">{catalog.comboNote}</p>
        </section>
      )}

      {catalog && <p className="mt-8 whitespace-pre-line text-[11px] leading-relaxed text-muted">{catalog.priceNote}{"\n"}Prices and availability on foxtale.in can change. <Link className="font-bold underline" to="/how-it-works">How products are chosen</Link>.</p>}
    </div>
  );
}
