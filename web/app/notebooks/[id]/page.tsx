import { Shell } from '@/components/shell/Shell';

interface PageProps {
  params: { id: string };
}

export default function NotebookPage({ params }: PageProps) {
  return <Shell notebookId={params.id} />;
}
