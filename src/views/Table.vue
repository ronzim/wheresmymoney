<template>
  <v-container fluid>
    <!-- <v-row>
          <v-col cols="6"> // placeholder </v-col>
          <v-col cols="6"> // placeholder </v-col>
        </v-row> -->
    <v-row>
      <v-col>
        <v-data-table
          v-if="this.jsonData.length > 0"
          :headers="headers"
          :items="jsonData"
          dense
          :search="search"
          :item-class="rowClasses"
          :items-per-page="100"
          ref="table"
          id="table"
        >
          <template v-slot:item.identified="{ item }">
            <v-menu
              v-model="item.index"
              :close-on-content-click="true"
              left
              x-offset
            >
              <template v-slot:activator="{ on, attrs }">
                <span
                  :class="`${getColorFn(item.identified)}--text`"
                  v-bind="attrs"
                  v-on="on"
                  >{{ item.identified || "choose" }}</span
                >
              </template>
              <Categories
                :categories="categories"
                :getColorFn="getColorFn"
                :item="item"
              />
            </v-menu>
          </template>
          <template v-slot:item.tag="{ item }">
            <v-edit-dialog @open="open(item)">
              {{ item.tag }}
              <template v-slot:input>
                <v-text-field
                  v-model="item.tag"
                  label="Edit"
                  single-line
                  counter
                  @change="close(item)"
                ></v-text-field>
              </template>
            </v-edit-dialog>
          </template>
        </v-data-table>
      </v-col>
    </v-row>
  </v-container>
</template>

<script lang="ts">
import Vue, { PropType } from "vue";

import { Category, Message } from "@/types";
import { mapState } from "vuex";

import Categories from "@/components/Categories.vue";

export default Vue.extend({
  name: "Table",
  data: () => ({
    search: "" as string,
    changingData: "" as string,
    menu: false
  }),
  components: { Categories },
  props: {
    categories: { type: [] as PropType<Category[]>, required: true },
    getColorFn: {
      type: [] as PropType<(arg0: string) => string>,
      required: true
    }
  },
  computed: {
    ...mapState(["jsonData"]),
    headers: function () {
      let h = Object.keys(this.jsonData[0]).map(d => ({
        text: d,
        value: d,
        width: "50"
      }));
      let identifiedIndex = h.findIndex(str => str.value == "identified");
      h[identifiedIndex].text = "Categoria";
      console.log("headers", h);
      return h;
    },
    categoryNames: function () {
      return this.categories.map(c => c.name);
    }
  },
  methods: {
    rowClasses(item) {
      if (item.identified === undefined) {
        return "orange"; //can also return multiple classes e.g ["orange","disabled"]
      }
    },
    // save() {
    //   console.log("open");
    // },
    // cancel() {
    //   console.log("cancel");
    // },
    open(item) {
      console.log("open", item);
      console.log(this.jsonData);
      console.log(this.jsonData.indexOf(item));
    },
    close(item) {
      const index = this.jsonData.indexOf(item);
      console.log("close", item.tag, item.identified, index);
      this.$store.commit("updateData", [index, item]);
    }
  }
});
</script>

<style>
.orange {
  background-color: orange;
}
</style>
