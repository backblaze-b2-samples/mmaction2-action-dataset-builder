import { BuildEdit } from "@/components/builds/build-edit";

export default async function EditBuildPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <BuildEdit buildId={id} />;
}
