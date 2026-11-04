import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
export function Brand() {
  return (
    <Link href="/" className="brand" aria-label="Uploadio home">
      <span className="brand-icon">
        <ArrowUpRight size={24} strokeWidth={2.5} />
      </span>
      uploadio<span style={{ color: "var(--accent)", marginLeft: -9 }}>.</span>
    </Link>
  );
}
