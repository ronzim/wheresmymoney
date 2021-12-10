<template>
  <v-dialog v-model="dialog" persistent max-width="600px">
    <template v-slot:activator="{ on, attrs }">
      <v-btn color="secondary" v-bind="attrs" v-on="on" icon outlined>
        <v-icon>mdi-cog</v-icon>
      </v-btn>
    </template>
    <v-card>
      <v-card-title>
        <span class="text-h5 secondary--text">Categories</span>
        <v-spacer></v-spacer>
        <v-btn color="secondary" icon outlined @click="addRow">
          <v-icon color="secondary">mdi-plus</v-icon>
        </v-btn>
        <v-btn
          color="secondary"
          icon
          outlined
          @click="downloadJson"
          class="ml-2"
        >
          <v-icon>mdi-download</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>
        <v-data-table
          :headers="headers"
          :items="categories"
          dense
          height="500px"
        >
          <template v-slot:item.name="props">
            <v-edit-dialog
              :return-value.sync="props.item.name"
              @save="log"
              @cancel="log"
              @open="log"
              @close="log"
            >
              {{ props.item.name.toUpperCase() }}
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
              persistent
              @save="log"
              @cancel="log"
              @open="log"
              @close="log"
            >
              <v-chip
                small
                outlined
                v-for="(tag, index) in props.item.tags"
                :key="index"
              >
                {{ tag }}
              </v-chip>
              <template v-slot:input>
                <v-text-field
                  :value="props.item.tags"
                  @change="onTagsChange($event, props)"
                  @input="log"
                  label="Edit"
                  single-line
                  counter
                  autofocus
                ></v-text-field>
              </template>
            </v-edit-dialog>
          </template>
          <template v-slot:item.color="props">
            <v-menu open-on-hover top offset-y>
              <template v-slot:activator="{ on, attrs }">
                <v-btn
                  icon
                  :color="props.item.color"
                  dark
                  v-bind="attrs"
                  v-on="on"
                >
                  <v-icon>mdi-circle</v-icon>
                </v-btn>
              </template>

              <v-card>
                <v-color-picker
                  v-model="props.item.color"
                  class="ma-2"
                  :swatches="swatches"
                  show-swatches
                  hide-canvas
                  hide-inputs
                  hide-sliders
                ></v-color-picker
              ></v-card>
            </v-menu>
          </template>
        </v-data-table>
      </v-card-text>
      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn color="secondary" text @click="dialog = false"> Close </v-btn>
        <v-btn color="secondary" text @click="dialog = false"> Save </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import Vue from "vue";
import categories from "@/categories";

export default Vue.extend({
  name: "App",
  data: () => ({
    dialog: false,
    categories: categories,
    swatches: [
      ["#FF0000", "#AA0000", "#550000"],
      ["#FFFF00", "#AAAA00", "#555500"],
      ["#00FF00", "#00AA00", "#005500"],
      ["#00FFFF", "#00AAAA", "#005555"],
      ["#0000FF", "#0000AA", "#000055"]
    ]
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
    },
    addRow: () => {
      categories.unshift({
        name: "",
        tags: [],
        color: "#000000"
      });
    },
    downloadJson: function () {
      let dataStr =
        "data:text/json;charset=utf-8," +
        encodeURIComponent(JSON.stringify(this.categories));
      let downloadAnchorNode = document.createElement("a");
      downloadAnchorNode.setAttribute("href", dataStr);
      downloadAnchorNode.setAttribute("download", "ciccio" + ".json");
      document.body.appendChild(downloadAnchorNode); // required for firefox
      downloadAnchorNode.click();
      downloadAnchorNode.remove();
    },
    onTagsChange: function (newValueString: any, event: any) {
      console.log("change", event, newValueString);
      let newTags = newValueString.split(",");
      console.log(newTags);
      this.categories[event.index].tags = newTags;
    }
  }
});
</script>
