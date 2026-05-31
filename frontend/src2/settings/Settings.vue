<script setup lang="ts">
import { Building2, CircleUser, DatabaseZap, KeyRound, SettingsIcon, Users } from 'lucide-vue-next'
import { defineAsyncComponent } from 'vue'
import { SettingsDialog } from 'frappe-ui'
import type { SettingsSection } from 'frappe-ui'
import { __ } from '../translation'

const showDialog = defineModel({ required: true, default: false })

const sections: SettingsSection[] = [
	{
		label: __('Account'),
		items: [
			{
				label: __('Profile'),
				icon: CircleUser,
				component: defineAsyncComponent(() => import('./ProfileSettings.vue')),
			},
		],
	},
	{
		label: __('Organization'),
		items: [
			{
				label: __('General'),
				icon: SettingsIcon,
				component: defineAsyncComponent(() => import('./GeneralSettings.vue')),
			},
			{
				label: __('Users'),
				icon: Users,
				component: defineAsyncComponent(() => import('./UsersSettings.vue')),
			},
			{
				label: __('Permissions'),
				icon: KeyRound,
				component: defineAsyncComponent(() => import('./PermissionsSettings.vue')),
			},
			{
				label: __('Data Store'),
				icon: DatabaseZap,
				component: defineAsyncComponent(() => import('./DataStoreSettings.vue')),
			},
		],
	},
]
</script>

<template>
	<SettingsDialog v-model="showDialog" :sections="sections" />
</template>
