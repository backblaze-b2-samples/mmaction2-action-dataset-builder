import { BuildDetail } from "@/components/builds/build-detail";

export default async function BuildDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <BuildDetail buildId={id} />;
}
