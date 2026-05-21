import { redirect } from 'next/navigation';

// The slice has one hardcoded notebook. Multi-notebook routing + a
// notebook picker land in P1 §1.8 (accounts & persistence).
export default function Home() {
  redirect('/notebooks/demo');
}
