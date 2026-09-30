import { EmptyState, PageHeader } from "../components/States";

export interface PlannedPageProps {
  eyebrow: string;
  title: string;
  lede: string;
  phase: string;
  features: string[];
}

/** Screen shell for capabilities scheduled in later build phases. Shows no figures: nothing is loaded yet. */
export function PlannedPage({ eyebrow, title, lede, phase, features }: PlannedPageProps) {
  return (
    <div className="stack">
      <PageHeader eyebrow={eyebrow} title={title} lede={lede} />
      <EmptyState title="No data loaded yet">
        This screen is built in {phase}. It reads only from the governance database, so it stays empty until
        that data exists.
      </EmptyState>
      <section className="panel">
        <h4>Planned contents <small>{phase}</small></h4>
        <ul className="checklist">
          {features.map((f) => <li key={f}>{f}</li>)}
        </ul>
      </section>
    </div>
  );
}
