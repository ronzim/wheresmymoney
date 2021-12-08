<template>
  <v-row justify="center">
    <v-dialog v-model="dialog" persistent max-width="600px">
      <template v-slot:activator="{ on, attrs }">
        <v-btn color="secondary" v-bind="attrs" v-on="on" icon outlined>
          <v-icon>mdi-cog</v-icon>
        </v-btn>
      </template>
      <v-card>
        <v-card-title>
          <span class="text-h5">Categories</span>
        </v-card-title>
        <v-card-text>
          <v-container>
            <v-row>
              <v-col cols="12">
                <v-data-table :headers="headers" :items="categories">
                  <template v-slot:item.name="props">
                    <v-edit-dialog
                      :return-value.sync="props.item.name"
                      @save="log"
                      @cancel="log"
                      @open="log"
                      @close="log"
                    >
                      {{ props.item.name }}
                      <template v-slot:input>
                        <v-text-field
                          v-model="props.item.name"
                          label="Edit"
                          single-line
                          counter
                        ></v-text-field>
                      </template>
                    </v-edit-dialog>
                  </template>
                  <template v-slot:item.tags="props">
                    <v-edit-dialog
                      :return-value.sync="props.item.tags"
                      large
                      persistent
                      @save="log"
                      @cancel="log"
                      @open="log"
                      @close="log"
                    >
                      <div>{{ props.item.tags }}</div>
                      <template v-slot:input>
                        <div class="mt-4 text-h6">Update Tags</div>
                        <v-text-field
                          v-model="props.item.tags"
                          label="Edit"
                          single-line
                          counter
                          autofocus
                        ></v-text-field>
                      </template>
                    </v-edit-dialog>
                  </template>
                </v-data-table>
              </v-col>
            </v-row>
          </v-container>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="secondary" text @click="dialog = false"> Close </v-btn>
          <v-btn color="secondary" text @click="dialog = false"> Save </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-row>
</template>

<script lang="ts">
import Vue from "vue";
import categories from "@/categories";

export default Vue.extend({
  name: "App",
  data: () => ({
    dialog: false,
    categories: categories
  }),
  computed: {
    headers: function () {
      return Object.keys(this.categories[0]).map(c => ({
        text: c,
        value: c,
        align: "start"
      }));
    }
  },
  methods: {
    log: (somethingToSay: string) => {
      console.log(somethingToSay);
    }
  }
});
</script>
