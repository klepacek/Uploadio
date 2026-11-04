import Link from "next/link";
import {
  ArrowRight,
  CalendarDays,
  Check,
  Layers3,
  Play,
  ShieldCheck,
  Video,
} from "lucide-react";
import { Brand } from "@/components/brand";
import { Button } from "@/components/ui/button";
export default function Home() {
  return (
    <div className="landing">
      <nav className="landing-nav">
        <Brand />
        <div className="row">
          <Button asChild variant="ghost">
            <Link href="/login">Log in</Link>
          </Button>
          <Button asChild>
            <Link href="/register">
              Get started <ArrowRight size={15} />
            </Link>
          </Button>
        </div>
      </nav>
      <main>
        <section className="hero">
          <div>
            <div className="eyebrow">Less switching. More creating.</div>
            <h1>
              Your content.
              <br />A little more
              <br />
              <span>everywhere.</span>
            </h1>
            <p>
              A focused workspace to prepare videos, plan your calendar, and
              keep track of every destination.
            </p>
            <div className="actions" style={{ marginTop: 28 }}>
              <Button asChild>
                <Link href="/register">
                  Create your workspace <ArrowRight size={16} />
                </Link>
              </Button>
              <Button asChild variant="outline">
                <Link href="/login">Open Uploadio</Link>
              </Button>
            </div>
            <p className="subtle" style={{ marginTop: 20 }}>
              Instagram and TikTok integrations require approved platform
              access.
            </p>
          </div>
          <div
            className="hero-art"
            aria-label="Illustration of a publishing workflow"
          >
            <div className="row spread">
              <span className="eyebrow">One video. Your next move.</span>
              <Video size={18} />
            </div>
            <div className="mock-video">
              <Play size={56} fill="#cbef80" color="#cbef80" />
            </div>
            <div className="panel-body" style={{ padding: 0 }}>
              <h2>Make room for the good stuff.</h2>
              <p>Prepare once. Choose each destination.</p>
              <div className="row spread">
                <span className="badge">Reels</span>
                <span className="badge">Stories</span>
                <span className="badge">TikTok</span>
                <Check size={18} color="#cbef80" />
              </div>
            </div>
          </div>
        </section>
        <section className="feature-grid">
          <article>
            <Layers3 />
            <h2>One calm workspace</h2>
            <p>
              Your videos, captions, destinations, and publishing history, in
              one place.
            </p>
          </article>
          <article>
            <CalendarDays />
            <h2>A plan you can see</h2>
            <p>
              Keep drafts close and scheduled content in view with a clear
              publishing calendar.
            </p>
          </article>
          <article>
            <ShieldCheck />
            <h2>Connected the right way</h2>
            <p>
              Official authorization flows, private media, and a separate result
              for every destination.
            </p>
          </article>
        </section>
      </main>
      <footer className="footer">
        <span>© {new Date().getFullYear()} Uploadio · Vojtěch Klepáček</span>
        <a href="https://github.com/klepacek/Uploadio">Project on GitHub ↗</a>
      </footer>
    </div>
  );
}
