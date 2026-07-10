<template>
	<header class="sticky top-0 z-10 flex items-center justify-between bg-white px-5 py-2.5">
		<PageBreadcrumbs
			class="h-7"
			:items="[
				{ label: __('Data Sources'), route: { path: '/data-source' } },
				{ label: dataSource.doc.title },
			]"
		/>
	</header>

	<div class="mb-4 flex h-full flex-col gap-2 overflow-auto px-4">
		<div class="flex gap-2 overflow-visible py-1">
			<FormControl :placeholder="__('Search by Title')" v-model="searchQuery" :debounce="300">
				<template #prefix>
					<SearchIcon class="h-4 w-4 text-gray-500" />
				</template>
			</FormControl>
			<Button
				variant="outline"
				iconLeft="link-2"
				@click="router.push(`/data-source/${dataSource.doc.name}/relationships`)"
			>
				{{ __('Manage Relationships') }}
			</Button>
			<Dropdown
				placement="left"
				:button="{ icon: 'more-horizontal', variant: 'outline' }"
				:options="dropdownActions"
			/>
		</div>
		<ListView
			:columns="tableListColumns"
			:rows="filteredTableList"
			:row-key="'name'"
			:options="{
				showTooltip: false,
				getRowRoute: (table) => ({
					name: 'DataSourceTable',
					params: { name: dataSource.doc.name, table: table.name },
				}),
				emptyState: {
					title: __('No tables.'),
					description: __('No tables to display.'),
					button: {
						label: __('Sync Tables'),
						variant: 'solid',
						onClick: syncTables,
					},
				},
			}"
		>
		</ListView>
	</div>

	<Dialog
		v-model="showDeleteDialog"
		:dismissable="true"
		:options="{
			title: __('Delete Data Source'),
			message: __('Are you sure you want to delete this data source?'),
			icon: { name: 'trash', appearance: 'danger' },
			actions: [
				{
					label: __('Delete'),
					variant: 'solid',
					theme: 'red',
					onClick: async () => {
						await dataSource.delete()
						router.push({ name: 'DataSourceList' })
					},
				},
			],
		}"
	>
	</Dialog>
</template>

<script setup lang="jsx">
import IndicatorIcon from '@/components/Icons/IndicatorIcon.vue'
import PageBreadcrumbs from '@/components/PageBreadcrumbs.vue'
import { ListView } from 'frappe-ui'
import { SearchIcon } from 'lucide-vue-next'
import { computed, inject, provide, ref, watchEffect } from 'vue'
import { useRouter } from 'vue-router'
import useDataSource from './useDataSource'

const props = defineProps({
	name: {
		type: String,
		required: true,
	},
})

const router = useRouter()
const dataSource = useDataSource(props.name)
provide('dataSource', dataSource)
dataSource.fetchTables()

const searchQuery = ref('')
const filteredTableList = computed(() => {
	const tableList = dataSource.tableList.filter((t) => !t.is_query_based)
	if (!tableList.length) return []
	if (!searchQuery.value) return tableList
	return tableList.filter((table) => {
		return table.label.toLowerCase().includes(searchQuery.value.toLowerCase())
	})
})

const showDeleteDialog = ref(false)
const dropdownActions = computed(() => {
	return [
		{
			label: __('Sync Tables'),
			icon: 'refresh-cw',
			onClick: syncTables,
		},
		{
			label: __('Delete'),
			icon: 'trash',
			onClick: () => (showDeleteDialog.value = true),
		},
	]
})

const $notify = inject('$notify')
function syncTables() {
	dataSource
		.syncTables()
		.catch((err) => $notify({ title: __('Error Syncing Tables'), variant: 'error' }))
}

watchEffect(() => {
	if (dataSource.doc?.name) {
		const title = dataSource.doc.title || dataSource.doc.name
		document.title = `${title} - Frappe Insights`
	}
})

const tableListColumns = [
	{ label: __('Table'), key: 'label' },
	{
		label: __('Status'),
		key: 'status',
		getLabel: ({ row }) => (row.hidden ? __('Disabled') : __('Enabled')),
		prefix: ({ row }) => {
			const color = row.hidden ? 'text-gray-500' : 'text-green-500'
			return <IndicatorIcon class={color} />
		},
	},
]
</script>
