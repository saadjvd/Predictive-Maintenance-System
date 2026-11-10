import EquipmentDetailClient from './equipment-detail-client'

export function generateStaticParams() {
  return [
    { id: 'default' },
  ]
}

export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const resolvedParams = await params
  return <EquipmentDetailClient initialId={resolvedParams.id} />
}
