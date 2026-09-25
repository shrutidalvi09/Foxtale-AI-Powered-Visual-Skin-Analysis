import { Link } from "react-router-dom";
import { Compass } from "lucide-react";
import type { ReactNode } from "react";
import { EmptyState, PageHeader } from "../components/ui";

function Doc({ title, updated, children }: { title: string; updated?: string; children: ReactNode }) {
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title={title} subtitle={updated ? `Last updated ${updated}` : undefined} />
      <div className="card space-y-5 p-6 text-[14.5px] leading-relaxed text-ink sm:p-8 [&_h2]:mt-2 [&_h2]:text-lg [&_h2]:font-extrabold [&_ul]:list-disc [&_ul]:space-y-1.5 [&_ul]:pl-5">
        {children}
      </div>
    </div>
  );
}

export function PrivacyPolicy() {
  return (
    <Doc title="Privacy Policy" updated="September 2026">
      <p className="rounded-2xl bg-soft p-4 text-sm text-muted">This is a plain-language template describing how this app works today. Have it reviewed by a legal adviser before you publish the app to the public.</p>
      <h2>What we collect</h2>
      <ul>
        <li>The photo you capture or upload, used to produce your analysis.</li>
        <li>Your analysis results, notes, routine ticks and answers to the profile questions.</li>
        <li>Your WhatsApp number, only if you choose to receive reports there, after you verify it with a code.</li>
      </ul>
      <h2>Where it is processed and stored</h2>
      <p>Photos are analysed by the Foxtale server that you run (on your own computer or your own hosting). Results are stored in that server's database. Photos are saved only when you turn on "Save scan photos". Nothing is sent to advertising or analytics services.</p>
      <h2>WhatsApp reports</h2>
      <p>If you register a number, each report (scores, findings, product suggestions and a PDF that can include your scan photo) is sent through WhatsApp, which is operated by Meta and has its own privacy terms. You can turn automatic sending off or remove your number at any time in Privacy.</p>
      <h2>Your choices</h2>
      <ul>
        <li>Turn scan history and photo saving on or off.</li>
        <li>Export everything, import a backup, or delete all data from the Privacy page.</li>
        <li>Deleted scans stay in "Recently deleted" for 30 days and are then removed.</li>
      </ul>
      <h2>Sensitive information</h2>
      <p>Face photos and skin observations are sensitive. Keep your server and its data folder secure, and do not share reports you do not want others to see.</p>
      <h2>Contact</h2>
      <p>Questions or requests about your data: contact the operator of this app.</p>
    </Doc>
  );
}

export function Terms() {
  return (
    <Doc title="Terms of Use" updated="September 2026">
      <p className="rounded-2xl bg-soft p-4 text-sm text-muted">Template terms for a personal or prototype deployment. Have them reviewed before public release.</p>
      <h2>Not medical advice</h2>
      <p>Foxtale describes visible features in a photo using computer vision. It does not diagnose any condition and is not a substitute for a doctor or dermatologist. If a skin change is painful, spreading, bleeding, changing quickly or worrying, see a qualified professional.</p>
      <h2>Accuracy</h2>
      <p>Results are estimates. Lighting, camera quality, makeup, hair, glasses and head angle affect them. Do not rely on them for treatment decisions.</p>
      <h2>Product suggestions</h2>
      <p>Suggestions are general cosmetic guidance based on your scan and answers. Always read the product label, patch-test new products and stop use if irritation occurs. Prices and availability come from foxtale.in and can change; the final price is the one on the store.</p>
      <h2>Your responsibility</h2>
      <ul>
        <li>Only scan yourself, or someone who has agreed.</li>
        <li>Keep your account and server secure.</li>
      </ul>
    </Doc>
  );
}

const FAQ: [string, string][] = [
  ["How does Foxtale analyse my skin?", "It finds your face, separates skin from eyes, brows, hair and lips, evens out the lighting, and measures colour and brightness on the skin in a colour space designed to match human vision. Spots, dark patches, pores, lines and shine are found with image processing, not a black-box model."],
  ["How accurate is it?", "It is an estimate from one photo. Good, even, front-facing light and a clean face give the best results. Pores, blackheads and scarring are the hardest to judge on a webcam; puffiness cannot be judged from a flat photo, so it is not scored."],
  ["Why does my skin tone change between scans?", "The tone shown is how your skin appears in that photo. Lighting and your camera's colour settings change it, so scan in similar light each time."],
  ["How are products chosen?", "Each Foxtale product is tagged with what it helps. Your findings decide which products score highest, your profile answers remove anything unsafe for you (pregnancy, sensitivity, allergies) and rank by goals and budget, and only one strong active is suggested at a time."],
  ["Is my data private?", "Photos are analysed on your own server. Nothing goes to advertisers or analytics. If you use WhatsApp delivery, the report travels through WhatsApp (Meta). See the Privacy Policy."],
  ["Can it tell me if I have acne, a disease or a skin condition?", "No. It reports what is visible, such as spots that look like pimples. It cannot diagnose. Please see a dermatologist for medical questions."],
];

export function HowItWorks() {
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="How it works and FAQ" subtitle="What Foxtale measures, how, and how far to trust it." />
      <div className="space-y-3">
        {FAQ.map(([q, a]) => (
          <details key={q} className="card group p-5 open:border-fox-300">
            <summary className="cursor-pointer list-none text-[15px] font-extrabold text-ink marker:hidden">{q}</summary>
            <p className="mt-3 text-sm leading-relaxed text-muted">{a}</p>
          </details>
        ))}
      </div>
      <p className="mt-6 text-sm text-muted">More: <Link className="font-bold text-fox-text underline dark:text-fox-300" to="/privacy-policy">Privacy Policy</Link> · <Link className="font-bold text-fox-text underline dark:text-fox-300" to="/terms">Terms of Use</Link></p>
    </div>
  );
}

export function NotFound() {
  return (
    <EmptyState
      icon={<Compass size={28} />} title="Page not found" body="That page does not exist. Let's get you back on track."
      action={<Link to="/" className="btn-cta">Go to dashboard</Link>}
    />
  );
}
